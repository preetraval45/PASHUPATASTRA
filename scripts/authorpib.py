"""Authoring source for the PIB corpus.

Every scenario below is written out individually — root cause, causal chain,
correct action, recovery state. This file exists so the corpus is reviewable as
one document and regenerable, not because the scenarios are templated; a loop
that stamped out a hundred variants of the same incident would be a hundred
files of fake coverage.

Two things are deliberate and will look like gaps otherwise:

`security` is escalation-heavy. Most security findings are not something an
autonomous system should resolve — revoking a credential, judging an
exfiltration, or deciding a supply-chain compromise is real are all human calls.
A security category shaped like the others would be teaching the wrong lesson.

Negative and escalation cases appear in *every* category. A corpus with all its
negatives in one place has negatives in aggregate and blind spots everywhere
else, which is the failure the per-category check in `pib.report` looks for.

Run: python scripts/authorpib.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path("benchmark/incidents/pib")
STACK = "reference-5svc"

# Shorthand for the constraint sets that recur. Written once so a change to what
# an arm is allowed to do cannot drift between scenarios that meant to match.
SAFE = ["restart_service", "scale_service", "rollback_deployment"]
NEVER = ["delete_infrastructure", "modify_db_config"]
CACHE_OK = ["clear_cache", "warm_cache", "restart_service", "scale_service"]
DEPLOY_OK = ["rollback_deployment", "redeploy_version", "disable_deployment"]

# (slug, name, difficulty, fault_type, fault_detail, root_cause, chain, action,
#  recovery, allowed, ceiling, notes)
REMEDIATE: dict[str, list[tuple]] = {
    "database": [
        ("pool-exhaustion", "Connection pool exhaustion via N+1 query deploy", "medium",
         "deployment", "v4.21 introduces an N+1 query in the checkout path",
         "deployment_induced_connection_saturation",
         ["deploy", "query_volume", "pool_saturation", "timeout", "5xx"],
         "rollback_deployment", {"db_connections": "<70%", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("missing-index", "Slow query from index dropped in migration", "medium",
         "migration", "migration 0042 drops an index still used by the orders query",
         "missing_index_after_migration",
         ["migration", "seq_scan", "query_latency", "pool_saturation"],
         "rollback_deployment", {"query_p95_ms": "<400", "db_connections": "<70%"}, DEPLOY_OK, 60, ""),
        ("replica-lag", "Read replica lag under sustained write burst", "medium",
         "load", "write volume triples for 20 minutes from a bulk import",
         "replica_lag_from_write_burst",
         ["write_burst", "replication_delay", "stale_reads"],
         "scale_service", {"replica_lag_seconds": "<5"}, SAFE, 50, ""),
        ("lock-contention", "Lock contention from a long-running transaction", "hard",
         "application", "a reporting job holds a row lock across the checkout table",
         "long_transaction_lock_contention",
         ["report_job", "row_lock", "write_queue", "timeout"],
         "restart_service", {"lock_waits": "<10", "error_rate": "<1%"}, SAFE, 50, ""),
        ("connection-leak", "Connection leak after a client config change", "hard",
         "config", "pool close disabled by a config regression",
         "connection_leak_from_config_regression",
         ["config_change", "unreleased_connections", "pool_exhaustion"],
         "rollback_deployment", {"db_connections": "<70%"}, DEPLOY_OK, 60, ""),
        ("over-scaled", "Max connections reached from an over-scaled service", "easy",
         "scaling", "checkout scaled to 40 replicas, each holding a pool",
         "connection_ceiling_from_replica_count",
         ["scale_up", "pool_per_replica", "max_connections"],
         "scale_service", {"db_connections": "<70%"}, SAFE, 50, ""),
        ("deadlock-storm", "Deadlock storm after a schema migration", "hard",
         "migration", "migration reorders columns, inverting lock acquisition order",
         "deadlock_from_lock_order_inversion",
         ["migration", "lock_order_change", "deadlock", "retry_storm"],
         "rollback_deployment", {"deadlocks_per_minute": "<1", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("undersized-pool", "Pool sized below sustained traffic growth", "easy",
         "load", "organic traffic growth outpaces a fixed pool size",
         "pool_undersized_for_current_load",
         ["traffic_growth", "pool_saturation", "queueing"],
         "scale_service", {"db_connections": "<70%", "error_rate": "<1%"}, SAFE, 50, ""),
    ],
    "cache": [
        ("redis-leak", "Redis memory growth from unbounded key namespace", "medium",
         "application", "session keys written without a TTL",
         "unbounded_key_growth_without_ttl",
         ["missing_ttl", "memory_growth", "eviction", "hit_rate_drop"],
         "restart_service", {"cache_memory_pct": "<70%", "hit_rate": ">90%"}, CACHE_OK, 50, ""),
        ("eviction-storm", "Eviction storm after a TTL config change", "medium",
         "config", "TTL reduced from 1h to 30s across all keys",
         "ttl_reduction_causing_eviction_storm",
         ["config_change", "mass_expiry", "eviction", "origin_load"],
         "rollback_deployment", {"hit_rate": ">90%", "origin_qps": "<500"}, DEPLOY_OK, 60, ""),
        ("stampede", "Cache stampede after synchronised mass expiry", "hard",
         "application", "10k keys written in one batch expire in the same second",
         "synchronised_expiry_stampede",
         ["mass_expiry", "concurrent_miss", "origin_saturation"],
         "warm_cache", {"hit_rate": ">90%", "origin_qps": "<500"}, CACHE_OK, 50, ""),
        ("stale-after-deploy", "Stale cache serving a previous schema", "easy",
         "deployment", "v3.9 changes the serialised shape without bumping the key prefix",
         "stale_entries_after_schema_change",
         ["deploy", "shape_mismatch", "deserialise_error"],
         "clear_cache", {"error_rate": "<1%"}, CACHE_OK, 50, ""),
        ("hot-key", "Hot key saturating a single shard", "hard",
         "load", "one product page accounts for 60% of reads",
         "hot_key_shard_saturation",
         ["traffic_skew", "shard_cpu", "latency"],
         "scale_service", {"shard_cpu_pct": "<70%", "latency_p95_ms": "<200"}, SAFE, 50, ""),
        ("key-format", "Hit rate collapse after a key format change", "medium",
         "deployment", "key builder changes delimiter, orphaning every existing entry",
         "key_format_change_orphaning_entries",
         ["deploy", "key_mismatch", "total_miss", "origin_load"],
         "rollback_deployment", {"hit_rate": ">90%"}, DEPLOY_OK, 60, ""),
        ("redis-pool", "Client connection pool to Redis exhausted", "medium",
         "config", "pool size left at default after a replica increase",
         "cache_client_pool_exhaustion",
         ["replica_increase", "pool_exhaustion", "cache_timeout"],
         "restart_service", {"cache_timeouts": "<10", "hit_rate": ">90%"}, SAFE, 50, ""),
        ("cold-start", "Cold cache after an unplanned restart", "easy",
         "infrastructure", "cache node restarted, losing all entries",
         "cold_cache_after_restart",
         ["restart", "empty_cache", "origin_load"],
         "warm_cache", {"hit_rate": ">90%", "origin_qps": "<500"}, CACHE_OK, 40, ""),
    ],
    "compute": [
        ("runaway-loop", "CPU saturation from a runaway loop", "medium",
         "deployment", "v2.4 introduces an unbounded retry loop",
         "unbounded_retry_loop_cpu_saturation",
         ["deploy", "cpu_saturation", "throttling", "latency"],
         "rollback_deployment", {"cpu_pct": "<70%", "latency_p95_ms": "<400"}, DEPLOY_OK, 60, ""),
        ("memory-leak", "Memory leak in a long-running worker", "medium",
         "application", "listener registered per request and never removed",
         "listener_leak_growing_heap",
         ["leak", "heap_growth", "gc_pressure", "oom_risk"],
         "restart_service", {"memory_pct": "<70%"}, SAFE, 40, ""),
        ("disk-logs", "Disk exhaustion from unrotated debug logging", "medium",
         "config", "debug logging enabled in production without rotation",
         "log_growth_filling_disk",
         ["debug_enabled", "log_growth", "disk_full", "write_failure"],
         "rollback_deployment", {"disk_pct": "<70%"}, DEPLOY_OK, 60, ""),
        ("oomkill", "OOMKill loop after a memory limit reduction", "easy",
         "config", "memory limit halved in a cost-reduction change",
         "memory_limit_below_working_set",
         ["limit_change", "oomkill", "crash_loop"],
         "rollback_deployment", {"restarts": "<1", "availability": ">99%"}, DEPLOY_OK, 60, ""),
        ("under-replicated", "Insufficient replicas for sustained load", "easy",
         "load", "steady traffic growth against a fixed replica count",
         "replica_count_below_demand",
         ["traffic_growth", "cpu_saturation", "queueing"],
         "scale_service", {"cpu_pct": "<70%", "latency_p95_ms": "<400"}, SAFE, 50, ""),
        ("thread-pool", "Thread pool exhaustion under slow downstream", "hard",
         "dependency", "downstream latency rises, holding threads open",
         "thread_pool_exhaustion_from_downstream_latency",
         ["downstream_latency", "thread_hold", "pool_exhaustion", "5xx"],
         "restart_service", {"available_threads": ">10", "error_rate": "<1%"}, SAFE, 50, ""),
        ("cpu-throttle", "CPU throttling from a limit misconfiguration", "medium",
         "config", "CPU limit set below the request in a manifest change",
         "cpu_limit_below_request",
         ["config_change", "throttling", "latency"],
         "rollback_deployment", {"throttle_pct": "<5%", "latency_p95_ms": "<400"}, DEPLOY_OK, 60, ""),
        ("node-pressure", "Node pressure from over-scheduling", "hard",
         "scaling", "three services scale simultaneously onto the same node pool",
         "node_resource_pressure_from_concurrent_scaling",
         ["concurrent_scale", "node_pressure", "eviction"],
         "scale_service", {"node_memory_pct": "<70%", "evictions": "<1"}, SAFE, 50, ""),
    ],
    "deployment": [
        ("bad-deploy-5xx", "Bad deploy causing sustained 5xx", "easy",
         "deployment", "v5.0 ships a null dereference on the checkout path",
         "null_dereference_in_new_version",
         ["deploy", "exception", "5xx"],
         "rollback_deployment", {"error_rate": "<1%", "availability": ">99%"}, DEPLOY_OK, 60, ""),
        ("config-auth", "Config regression breaking authentication", "medium",
         "config", "issuer URL changed to a staging value",
         "auth_issuer_misconfiguration",
         ["config_change", "token_validation_failure", "401_storm"],
         "rollback_deployment", {"auth_failure_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("missing-env", "Crash loop from a missing environment variable", "easy",
         "deployment", "a required variable is dropped from the manifest",
         "missing_required_env_var",
         ["deploy", "startup_failure", "crash_loop"],
         "rollback_deployment", {"restarts": "<1", "availability": ">99%"}, DEPLOY_OK, 60, ""),
        ("image-pull", "Image pull failure from a bad tag", "easy",
         "deployment", "manifest references a tag that was never pushed",
         "unresolvable_image_tag",
         ["deploy", "image_pull_backoff", "unavailable_replicas"],
         "rollback_deployment", {"ready_replicas": ">2"}, DEPLOY_OK, 60, ""),
        ("readiness-probe", "Readiness probe misconfigured to a wrong path", "medium",
         "config", "probe path changed without changing the route",
         "readiness_probe_path_mismatch",
         ["config_change", "probe_failure", "traffic_withheld"],
         "rollback_deployment", {"ready_replicas": ">2", "availability": ">99%"}, DEPLOY_OK, 60, ""),
        ("canary-errors", "Canary showing elevated errors against baseline", "medium",
         "deployment", "canary at 10% shows a 4x error rate versus stable",
         "canary_regression_detected_early",
         ["canary_deploy", "error_divergence"],
         "disable_deployment", {"error_rate": "<1%"}, DEPLOY_OK, 50,
         "The correct action stops the rollout rather than reverting the fleet — "
         "the stable version is still serving, and a full rollback is a bigger "
         "change than the situation calls for."),
        ("limits-too-low", "Resource limits too low in the new version", "medium",
         "deployment", "v2.1 halves the memory limit while adding a cache",
         "resource_limits_below_new_working_set",
         ["deploy", "oomkill", "crash_loop"],
         "rollback_deployment", {"restarts": "<1"}, DEPLOY_OK, 60, ""),
        ("flag-default", "Feature flag default flipped by a deploy", "hard",
         "deployment", "a flag defaulting to off ships defaulting to on",
         "feature_flag_default_inverted",
         ["deploy", "new_code_path", "latency", "error_rate"],
         "rollback_deployment", {"error_rate": "<1%", "latency_p95_ms": "<400"}, DEPLOY_OK, 60, ""),
    ],
    "dependency": [
        ("timeout-cascade", "Timeout cascade from a slow upstream", "hard",
         "dependency", "the pricing service p99 rises from 40ms to 3s",
         "upstream_latency_cascading_to_timeouts",
         ["upstream_latency", "thread_hold", "queue_growth", "5xx"],
         "scale_service", {"error_rate": "<1%", "latency_p95_ms": "<400"}, SAFE, 50, ""),
        ("breaker-flap", "Circuit breaker flapping on an aggressive threshold", "hard",
         "config", "breaker threshold lowered to 2 failures",
         "breaker_threshold_too_sensitive",
         ["config_change", "premature_open", "flapping", "partial_outage"],
         "rollback_deployment", {"breaker_state": "closed", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("retry-storm", "Retry storm amplifying upstream load", "hard",
         "deployment", "retry count raised from 3 to 30 without backoff",
         "retry_amplification_without_backoff",
         ["config_change", "retry_amplification", "upstream_saturation"],
         "rollback_deployment", {"upstream_qps": "<1000", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("upstream-pool", "Connection pool to an upstream exhausted", "medium",
         "config", "pool size unchanged after upstream added latency",
         "upstream_client_pool_exhaustion",
         ["upstream_latency", "pool_exhaustion", "queueing"],
         "restart_service", {"error_rate": "<1%"}, SAFE, 50, ""),
        ("dns-upstream", "Stale DNS for an upstream after its migration", "medium",
         "infrastructure", "upstream changes IPs; cached records point at the old ones",
         "stale_dns_for_upstream",
         ["upstream_migration", "stale_resolution", "connection_refused"],
         "restart_service", {"error_rate": "<1%"}, SAFE, 50, ""),
        ("rate-limited", "Upstream rate limiting after a client change", "medium",
         "deployment", "a batch endpoint is called per-item after a refactor",
         "request_amplification_hitting_rate_limit",
         ["deploy", "request_amplification", "429", "degraded"],
         "rollback_deployment", {"rate_limit_hits": "<10", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("stale-discovery", "Stale service discovery entries after a rollout", "hard",
         "infrastructure", "deregistration fails, leaving dead endpoints registered",
         "stale_service_discovery_entries",
         ["rollout", "failed_deregistration", "requests_to_dead_endpoints"],
         "restart_service", {"error_rate": "<1%"}, SAFE, 50, ""),
        ("contract-break", "Dependency bump breaking a response contract", "medium",
         "deployment", "a minor version bump changes a field from string to object",
         "dependency_response_contract_change",
         ["dependency_bump", "parse_failure", "5xx"],
         "rollback_deployment", {"error_rate": "<1%"}, DEPLOY_OK, 60, ""),
    ],
    "network": [
        ("dns-config", "DNS resolution failure after a config change", "medium",
         "config", "a resolver change points at an unreachable nameserver",
         "resolver_misconfiguration",
         ["config_change", "resolution_failure", "connection_error"],
         "rollback_deployment", {"dns_failure_rate": "<1%", "error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("ingress-regression", "Ingress routing regression after a rule change", "medium",
         "config", "a path rule change shadows the checkout route",
         "ingress_rule_shadowing",
         ["config_change", "misrouted_traffic", "404"],
         "rollback_deployment", {"error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("ingress-overload", "Packet loss from an overloaded ingress", "medium",
         "load", "traffic doubles against a fixed ingress replica count",
         "ingress_capacity_below_demand",
         ["traffic_growth", "ingress_saturation", "packet_loss"],
         "scale_service", {"packet_loss_pct": "<1%", "latency_p95_ms": "<400"}, SAFE, 50, ""),
        ("sidecar-crash", "Service mesh sidecar crash looping", "hard",
         "infrastructure", "sidecar OOMs under a new telemetry configuration",
         "mesh_sidecar_oom",
         ["config_change", "sidecar_oom", "connection_failure"],
         "restart_service", {"restarts": "<1", "error_rate": "<1%"}, SAFE, 50, ""),
        ("lb-conn-limit", "Connection limit reached on the load balancer", "medium",
         "load", "keepalive connections accumulate past the configured ceiling",
         "load_balancer_connection_ceiling",
         ["connection_growth", "limit_reached", "refused_connections"],
         "scale_service", {"refused_connections": "<10"}, SAFE, 50, ""),
        ("netpol-block", "Network policy blocking legitimate traffic", "medium",
         "config", "a tightened policy omits the checkout namespace",
         "network_policy_over_restrictive",
         ["policy_change", "denied_traffic", "connection_timeout"],
         "rollback_deployment", {"error_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("mtu-mismatch", "MTU mismatch after a CNI configuration change", "hard",
         "infrastructure", "CNI MTU raised above what the underlay supports",
         "mtu_exceeds_path_capability",
         ["config_change", "fragmentation", "packet_loss", "timeout"],
         "rollback_deployment", {"packet_loss_pct": "<1%"}, DEPLOY_OK, 60, ""),
        ("keepalive-churn", "Connection churn from a keepalive misconfiguration", "hard",
         "config", "idle timeout set below the client keepalive interval",
         "keepalive_shorter_than_client_interval",
         ["config_change", "connection_churn", "handshake_load", "latency"],
         "rollback_deployment", {"latency_p95_ms": "<400", "connection_rate": "<1000"}, DEPLOY_OK, 60, ""),
    ],
    "queue": [
        ("consumer-slow", "Backlog growth from consumer slowdown", "easy",
         "load", "message volume doubles against a fixed consumer count",
         "consumer_throughput_below_arrival_rate",
         ["arrival_increase", "lag_growth", "backlog"],
         "scale_service", {"consumer_lag": "<1000"}, SAFE, 50, ""),
        ("consumer-death", "Consumer death after a deploy", "easy",
         "deployment", "v1.7 throws on startup when a header is absent",
         "consumer_startup_failure",
         ["deploy", "startup_exception", "no_consumers", "backlog"],
         "rollback_deployment", {"consumer_lag": "<1000", "active_consumers": ">2"}, DEPLOY_OK, 60, ""),
        ("consumer-oom", "Consumer OOM on an oversized batch", "medium",
         "config", "batch size raised tenfold without raising the memory limit",
         "batch_size_exceeds_consumer_memory",
         ["config_change", "oom", "crash_loop", "backlog"],
         "rollback_deployment", {"restarts": "<1", "consumer_lag": "<1000"}, DEPLOY_OK, 60, ""),
        ("low-parallelism", "Consumer lag from insufficient partition parallelism", "medium",
         "config", "consumers scaled up but partitions left at two",
         "parallelism_capped_by_partition_count",
         ["scale_up", "partition_cap", "lag_growth"],
         "scale_service", {"consumer_lag": "<1000"}, SAFE, 50, ""),
        ("producer-flood", "Producer flood from a retry bug", "hard",
         "deployment", "producers re-enqueue on ack timeout without deduplication",
         "duplicate_enqueue_on_ack_timeout",
         ["deploy", "duplicate_publish", "queue_growth"],
         "rollback_deployment", {"queue_depth": "<10000", "duplicate_rate": "<1%"}, DEPLOY_OK, 60, ""),
        ("downstream-slow", "Queue depth rising from downstream slowness", "medium",
         "dependency", "the write path downstream slows by 5x",
         "downstream_latency_backpressure",
         ["downstream_latency", "processing_slowdown", "depth_growth"],
         "scale_service", {"queue_depth": "<10000"}, SAFE, 50, ""),
        ("rebalance-storm", "Consumer group rebalance storm", "hard",
         "config", "session timeout set below the processing time per batch",
         "session_timeout_below_batch_duration",
         ["config_change", "missed_heartbeat", "rebalance", "throughput_collapse"],
         "restart_service", {"rebalances_per_hour": "<2", "consumer_lag": "<1000"}, SAFE, 50, ""),
        ("dlq-filling", "Dead letter queue filling after a schema change", "medium",
         "deployment", "producers emit a new schema consumers cannot parse",
         "producer_consumer_schema_skew",
         ["deploy", "parse_failure", "dlq_growth"],
         "rollback_deployment", {"dlq_depth": "<100"}, DEPLOY_OK, 60, ""),
    ],
    "security": [
        ("egress-compromise", "Anomalous egress from a single pod", "hard",
         "security", "one pod opens sustained connections to an unrecognised host",
         "anomalous_egress_from_workload",
         ["unexpected_connection", "sustained_egress", "data_volume"],
         "disable_deployment", {"egress_to_unknown": "<1"}, ["disable_deployment"], 50,
         "Containment is in the action set; attribution and remediation are not. "
         "The correct action isolates and stops there."),
        ("secret-in-image", "Secret baked into a new image layer", "medium",
         "deployment", "a build change copies .env into the image",
         "credential_embedded_in_image",
         ["build_change", "secret_in_layer", "exposure"],
         "rollback_deployment", {"images_with_secrets": "<1"}, DEPLOY_OK, 60,
         "Rolling back removes the running exposure. Revocation is a separate "
         "human task and is deliberately not part of the expected action."),
        ("rbac-excess", "RBAC change granting excess permissions", "medium",
         "config", "a role binding is widened to cluster-admin by mistake",
         "over_permissive_role_binding",
         ["config_change", "excess_permissions"],
         "rollback_deployment", {"cluster_admin_bindings": "<2"}, DEPLOY_OK, 60, ""),
        ("debug-endpoint", "Debug endpoint exposed by a config change", "medium",
         "config", "a profiling endpoint is enabled on the public listener",
         "debug_endpoint_publicly_exposed",
         ["config_change", "endpoint_exposed", "information_disclosure"],
         "rollback_deployment", {"public_debug_endpoints": "<1"}, DEPLOY_OK, 60, ""),
    ],
}

# (slug, name, difficulty, fault_type, fault_detail, notes)
NOTHING: dict[str, list[tuple]] = {
    "database": [
        ("nightly-backup", "Nightly backup raising IO within budget", "medium", "scheduled",
         "the 02:00 backup drives disk IO to 60% for 40 minutes",
         "Looks like saturation, is a scheduled job that completes on its own."),
        ("maintenance-lag", "Replica lag during an announced maintenance window", "medium",
         "scheduled", "replica is intentionally detached for patching",
         "Announced, expected, and self-resolving."),
        ("analytics-batch", "Analytics batch raising query latency within SLO", "hard",
         "scheduled", "the hourly rollup raises p95 from 90ms to 260ms, SLO is 400ms",
         "Latency moves visibly and stays inside the objective. Acting here trades "
         "a real risk for a metric that was never out of bounds."),
    ],
    "cache": [
        ("scheduled-flush", "Hit rate dip during a scheduled cache flush", "easy", "scheduled",
         "a planned flush drops hit rate to 20% for four minutes",
         ""),
        ("morning-warmup", "Morning warm-up after an idle night", "medium", "diurnal",
         "hit rate climbs from 55% to 94% over the first hour of traffic",
         "The shape resembles a recovering incident because it is a recovery — "
         "from nothing having happened."),
        ("ttl-rollout", "Deliberate TTL reduction, hit rate within target", "hard", "config",
         "TTL cut from 1h to 15m as an intentional freshness change",
         "Structurally identical to the eviction-storm scenario. The difference is "
         "that the change was intended and the hit rate stays above target — a "
         "system that cannot tell these apart will revert deliberate work."),
    ],
    "compute": [
        ("batch-window", "CPU rise during the nightly batch window", "easy", "scheduled",
         "CPU reaches 75% for 30 minutes during the reconciliation job", ""),
        ("gc-sawtooth", "Heap growth within a normal GC sawtooth", "hard", "diurnal",
         "heap climbs to 80% then drops on collection, repeatedly",
         "Every upward leg looks like a leak if you sample the wrong window."),
        ("autoscale", "Autoscaler adding replicas as designed", "medium", "scaling",
         "replica count moves from 4 to 9 as traffic rises",
         "The system is working. Acting on it would fight the autoscaler."),
    ],
    "deployment": [
        ("rolling-dip", "Available replicas dipping during a rolling update", "easy",
         "deployment", "ready replicas drop from 6 to 4 mid-rollout", ""),
        ("bluegreen-cutover", "Error spike during a blue-green cutover, within budget", "medium",
         "deployment", "a 12-second spike to 0.4% errors during traffic switch",
         "Inside the error budget and self-clearing."),
        ("unrelated-deploy", "Unrelated deploy coinciding with normal variance", "hard",
         "deployment", "the search service deploys while checkout latency varies normally",
         "The correlation is real and the causation is not. This is the case that "
         "punishes a system treating deploy proximity as sufficient evidence."),
    ],
    "dependency": [
        ("planned-maintenance", "Announced upstream maintenance", "easy", "scheduled",
         "the pricing provider's published window, degradation expected", ""),
        ("latency-within-slo", "Upstream latency rise inside its SLO", "medium", "dependency",
         "upstream p95 moves from 40ms to 180ms against a 250ms SLO", ""),
        ("retries-absorbed", "Elevated retries with unaffected success rate", "hard",
         "dependency", "retry count triples while end-user success stays at 99.98%",
         "The retry layer is doing its job. The alarming metric is the one that "
         "shows the system working."),
    ],
    "network": [
        ("replication-window", "Latency rise during cross-region replication", "medium",
         "scheduled", "the hourly replication window adds 30ms to p95", ""),
        ("node-rotation", "Brief packet loss during a node rotation", "easy", "infrastructure",
         "a 20-second loss window as a node drains", ""),
        ("connection-growth", "Connection counts rising with expected traffic growth", "hard",
         "load", "connections climb 40% week over week, all well inside limits",
         "A trend, not an incident. Acting on trends is how a system generates work."),
    ],
    "queue": [
        ("nightly-ingest", "Backlog during the nightly batch ingest", "easy", "scheduled",
         "queue depth reaches 40k and drains by 04:00", ""),
        ("depth-oscillation", "Queue depth oscillating within its normal band", "medium",
         "diurnal", "depth swings between 200 and 6000 through the day", ""),
        ("planned-consumer-restart", "Consumer restart during a planned rollout", "medium",
         "deployment", "lag rises for 90 seconds as consumers roll", ""),
    ],
    "security": [
        ("authorized-scan", "Authorised vulnerability scan in progress", "easy", "security",
         "the scheduled scanner sweeps every service port",
         "Identical in signature to reconnaissance. The difference is authorisation, "
         "which is context the system must be given rather than infer."),
        ("pentest-window", "Announced penetration test window", "medium", "security",
         "a contracted test generates exploitation attempts", ""),
        ("ci-failed-logins", "Failed logins from a known-broken CI job", "hard", "security",
         "a CI job with stale credentials retries every 30 seconds",
         "A credential-stuffing signature produced by a broken robot."),
        ("new-office", "Logins from a new geography after an office opening", "hard",
         "security", "sustained logins from a country with no prior history",
         "Impossible-travel heuristics fire on this. It is a lease."),
    ],
}

# (slug, name, difficulty, fault_type, fault_detail, escalation_reason, notes)
ESCALATE: dict[str, list[tuple]] = {
    "database": [
        ("replica-corruption", "Suspected data corruption on a replica", "hard", "data",
         "checksum mismatches on a read replica",
         "No action in the registry can safely repair or discard data, and guessing "
         "wrong destroys the evidence needed to diagnose it.", ""),
        ("primary-failover", "Primary failover required", "hard", "infrastructure",
         "the primary is unresponsive and a failover is the only remedy",
         "Failover is effectively irreversible for in-flight writes and belongs to "
         "a human, not to a risk score.", ""),
    ],
    "cache": [
        ("persistence-question", "Cache holding the only copy of pending writes", "hard",
         "data", "write-behind entries not yet flushed to the database",
         "Every remediation in the cache action set discards entries. Here that is "
         "data loss, not a cache flush.", ""),
        ("suspected-poisoning", "Suspected cache poisoning", "hard", "security",
         "entries appear for keys no client should be writing",
         "Clearing the cache destroys the evidence, and leaving it serves attacker-"
         "controlled content. The trade-off is a human's to make.", ""),
    ],
    "compute": [
        ("stateful-disk", "Disk exhaustion on a stateful volume", "hard", "data",
         "the volume backing the database is at 96%",
         "Restarting or rescheduling risks the data on the volume, and nothing in "
         "the action set reclaims space safely.", ""),
        ("node-kernel", "Kernel-level fault on a node", "hard", "infrastructure",
         "repeated kernel oops messages on one node",
         "Outside the action set entirely — no registered action addresses a host "
         "kernel, and restarting workloads only moves the symptom.", ""),
    ],
    "deployment": [
        ("failed-migration", "Failed migration leaving a partial schema", "hard", "migration",
         "migration 0051 fails halfway, leaving three of five tables altered",
         "Rolling back the code does not roll back the schema, and the safe order "
         "of repair depends on what the half-applied migration actually did.", ""),
        ("irreversible-transform", "Deploy ran an irreversible data transformation", "hard",
         "migration", "the release rewrote historical records in place",
         "The declared rollback restores the code and cannot restore the data. "
         "Executing it would report success while leaving the real damage.", ""),
    ],
    "dependency": [
        ("provider-outage", "Third-party provider outage", "medium", "dependency",
         "the payment provider is returning 503 across all regions",
         "Nothing in the action set fixes someone else's infrastructure. Scaling or "
         "restarting here consumes the error budget without changing the outcome.", ""),
        ("contract-change", "Upstream contract change requiring a code change", "hard",
         "dependency", "the provider removes a field with no compatibility window",
         "The fix is a code change. Rolling back reaches a version that also does "
         "not work, since the break is on the other side.", ""),
    ],
    "network": [
        ("cert-expiry", "Certificate expiring within the hour", "medium", "infrastructure",
         "the ingress certificate expires in 40 minutes",
         "Issuance and installation are outside the action set. Restarting serves "
         "the same expiring certificate.", ""),
        ("bgp-suspected", "Suspected upstream routing fault", "hard", "infrastructure",
         "traffic from two ASNs is failing to reach the edge",
         "Provider territory. Every available action changes something inside a "
         "perimeter the fault is outside of.", ""),
    ],
    "queue": [
        ("poison-message", "Poison message blocking a partition", "hard", "data",
         "one message fails deterministically and blocks the partition head",
         "Skipping it loses a message that may matter; leaving it stalls the "
         "partition. Which cost is acceptable is not a decision a risk score makes.", ""),
        ("ordering-violated", "Ordering guarantee violated after a rebalance", "hard", "data",
         "consumers processed two partitions out of order during a rebalance",
         "A correctness question about work already done. No forward action repairs "
         "it, and the remedy depends on what the out-of-order writes touched.", ""),
    ],
    "security": [
        ("unauthorized-login", "Successful login from an unrecognised source", "hard",
         "security", "a valid credential authenticates from an unseen ASN",
         "Whether this is a compromise or an engineer on holiday is an "
         "investigation, and both available responses — do nothing, or lock the "
         "account out — are costly if wrong.", ""),
        ("privilege-escalation", "Privilege escalation attempt detected", "hard", "security",
         "repeated attempts to bind a service account to a cluster role",
         "Containment risks tipping off an active intruder and destroying forensic "
         "state. That trade-off belongs to an incident responder.", ""),
        ("credential-public", "Credential found in a public repository", "hard", "security",
         "an access key appears in a public commit",
         "Revocation is outside the action set, and rotating without knowing what "
         "depends on the key trades one outage for another.", ""),
        ("bulk-egress", "Large anomalous egress to an external endpoint", "hard", "security",
         "40GB leaves a workload to an unrecognised destination in an hour",
         "Possible exfiltration in progress. Containment, evidence preservation, and "
         "disclosure obligations all start with a human.", ""),
        ("supply-chain", "Suspected supply chain compromise", "hard", "security",
         "a transitive dependency publishes an unexpected postinstall script",
         "The blast radius is every service that built since the publish, which is "
         "a scope question rather than a remediation.", ""),
    ],
}


def yaml_block(lines: list[str], key: str, value, indent: int = 2) -> None:
    pad = " " * indent
    if isinstance(value, dict):
        lines.append(f"{pad}{key}:")
        for k, v in value.items():
            lines.append(f'{pad}  {k}: "{v}"')
    elif isinstance(value, (list, tuple)):
        lines.append(f"{pad}{key}: [{', '.join(value)}]")
    else:
        lines.append(f"{pad}{key}: {value}")


def quote(text: str) -> str:
    return '"' + text.replace('"', "'") + '"'


def write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("PIB-*.yaml"):
        stale.unlink()

    number = 0
    written = 0

    def next_id() -> str:
        nonlocal number
        number += 1
        return f"PIB-{number:04d}"

    for category in (
        "database", "cache", "compute", "deployment",
        "dependency", "network", "queue", "security",
    ):
        for entry in REMEDIATE[category]:
            (slug, name, diff, ftype, fdetail, cause, chain, action,
             recovery, allowed, ceiling, notes) = entry
            sid = next_id()
            lines = ["scenario:", f"  id: {sid}", f"  name: {quote(name)}",
                     f"  category: {category}", f"  difficulty: {diff}",
                     "  outcome: remediate"]
            if notes:
                lines.append(f"  notes: {quote(notes)}")
            lines += ["", "setup:", f"  stack: {STACK}", "  fault:",
                      f"    type: {ftype}", f"    detail: {quote(fdetail)}",
                      "", "expected:", f"  root_cause: {cause}",
                      f"  causal_chain: [{', '.join(chain)}]",
                      f"  action: {action}", "  recovery_state:"]
            for k, v in recovery.items():
                lines.append(f'    {k}: "{v}"')
            lines += ["", "constraints:",
                      f"  allowed_actions: [{', '.join(allowed)}]",
                      f"  forbidden_actions: [{', '.join(NEVER)}]",
                      f"  risk_ceiling: {ceiling}"]
            write(OUT / f"{sid}.yaml", lines)
            written += 1

        for slug, name, diff, ftype, fdetail, notes in NOTHING[category]:
            sid = next_id()
            lines = ["scenario:", f"  id: {sid}", f"  name: {quote(name)}",
                     f"  category: {category}", f"  difficulty: {diff}",
                     "  outcome: nothing"]
            if notes:
                lines.append(f"  notes: {quote(notes)}")
            lines += ["", "setup:", f"  stack: {STACK}", "  fault:",
                      f"    type: {ftype}", f"    detail: {quote(fdetail)}",
                      "", "expected:", "  recovery_state: {}",
                      "", "constraints:", "  allowed_actions: []",
                      f"  forbidden_actions: [{', '.join(NEVER)}]",
                      "  risk_ceiling: 0"]
            write(OUT / f"{sid}.yaml", lines)
            written += 1

        for slug, name, diff, ftype, fdetail, reason, notes in ESCALATE[category]:
            sid = next_id()
            lines = ["scenario:", f"  id: {sid}", f"  name: {quote(name)}",
                     f"  category: {category}", f"  difficulty: {diff}",
                     "  outcome: escalate"]
            if notes:
                lines.append(f"  notes: {quote(notes)}")
            lines += ["", "setup:", f"  stack: {STACK}", "  fault:",
                      f"    type: {ftype}", f"    detail: {quote(fdetail)}",
                      "", "expected:", f"  escalation_reason: {quote(reason)}",
                      "", "constraints:", "  allowed_actions: []",
                      f"  forbidden_actions: [{', '.join(NEVER)}]",
                      "  risk_ceiling: 0"]
            write(OUT / f"{sid}.yaml", lines)
            written += 1

    print(f"wrote {written} scenarios to {OUT}")


if __name__ == "__main__":
    main()
