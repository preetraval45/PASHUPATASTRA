"""Runtime configuration.

Credentials are never read from literals or committed files. On AWS they come
from Secrets Manager via IRSA; locally from a gitignored .env (see .env.example).
"""

from __future__ import annotations

from functools import lru_cache

from pashupatastra import Environment
from pashupatastra.dharma import ActionDomain
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PASHU_", env_file=".env", extra="ignore")

    environment: Environment = Environment.DEV

    dry_run: bool = True
    """Dry-run is the default. Live execution is opt-in per environment
    (docs/SECURITY.md, non-negotiable control 1)."""

    live_environments: list[Environment] = []
    """Environments where writes may actually reach a cluster. Empty by default.

    Two independent gates, deliberately: `dry_run` must be false *and* this
    environment must be listed. One flag is one accident away from a production
    write — someone flips `dry_run` for a local test, forgets, and deploys. Two
    gates mean a misconfiguration fails closed into dry-run rather than open."""

    kube_context: str | None = None
    """Explicit kubeconfig context for writes. `None` uses the active one.

    Worth setting in any environment that can reach more than one cluster: the
    active context is ambient state, and a cluster targeted by accident is the
    worst blast radius available."""

    database_url: str = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"
    redis_url: str = "redis://localhost:6379/0"
    opensearch_url: str = "http://localhost:9200"
    prometheus_url: str = "http://localhost:9090"

    dynamo_table: str | None = None
    """DynamoDB table to persist to. Empty means "no DynamoDB", and the stores
    fall back to Postgres or to memory.

    Chosen over RDS for the demo because DynamoDB's free allowance does not
    expire — see docs/REBUILD.md. A deployment with a real database should set
    `database_url` and leave this unset."""

    dynamo_namespace: str = "prod"
    """Which slice of the table this deployment owns.

    One table, several environments. DynamoDB's always-free allowance is 25
    capacity units per *account*, so a separate test table would take capacity
    away from the deployed one rather than add any — the namespace buys the same
    isolation for nothing.

    Set it to something other than `prod` for local work and tests. The default
    is deliberately the shared one: a deployment that forgets to set it still
    finds its own data, where a machine-specific default would silently give the
    Lambda an empty console after a redeploy."""

    aws_region: str = "us-east-1"
    artifacts_bucket: str | None = None

    model_provider: str = "echo"
    """Which provider the AI Gateway uses: `bedrock`, `anthropic`, or `echo`.

    Defaults to `echo` — the deterministic stub — so a fresh checkout runs with
    no credentials and cannot silently start spending money. Bedrock is the
    production target (the Platform ADR); the switch is configuration, never an
    import."""

    model_id: str = "claude-opus-5"
    """Named without a provider prefix. Bedrock's `anthropic.` prefix is applied
    by that provider, so switching providers does not require editing this."""

    tenant: str = "default"
    """Which organization this deployment serves.

    Single-tenant today, but memory is tenant-scoped from the first commit
    (ADR Smriti): retrofitting isolation is how leaks happen, so the argument
    exists and is threaded through even while there is only one value for it."""

    model_token_ceiling: int | None = 200_000
    """Per-incident token ceiling enforced by the gateway before each call.
    Mirrors the agent budget default in `packages/core/pashupatastra/agents.py`;
    `None` disables it."""

    action_domain: ActionDomain | None = None
    """Which action domain this deployment presents. `None` serves the whole
    registry.

    A view, never a second registry: `get` still resolves any registered id, so
    a plan written against one domain stays executable. What this changes is
    what an operator is offered, and offering a security console `restart_service`
    is how a domain re-theme ends up looking like a skin."""

    cors_origins: list[str] = ["http://localhost:3000"]

    demo_seed: bool = False
    """Replay `benchmark/incidents/` into the graph at startup.

    Off by default. A deployment with real connectors must never mix replayed
    corpus telemetry into its own topology — the events carry `source_system=
    "scenario"` provenance, but a graph is read as current state long before
    anyone opens an event's provenance."""

    @property
    def live_execution_enabled(self) -> bool:
        """Both gates, and the environment must be named explicitly.

        `not dry_run` alone is not enough — see `live_environments`.
        """
        return not self.dry_run and self.environment in self.live_environments


@lru_cache
def get_settings() -> Settings:
    return Settings()
