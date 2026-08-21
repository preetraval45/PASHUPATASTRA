"""The closed action registry.

Actions come from here, never from parsed model text (the Grounding ADR). Every entry
declares its risk, its expected post-state, and its rollback — an action without
a rollback cannot be autonomous.
"""

from __future__ import annotations

from .dharma import ActionDomain, ActionSpec

_ACTIONS: dict[str, ActionSpec] = {}


def register(action: ActionSpec) -> ActionSpec:
    if action.id in _ACTIONS:
        raise ValueError(f"action {action.id} already registered")
    if not action.irreversible and action.rollback_action_id is None and action.base_risk > 0:
        raise ValueError(
            f"action {action.id} has no rollback; declare one or mark it irreversible"
        )
    _ACTIONS[action.id] = action
    return action


def get(action_id: str) -> ActionSpec:
    if action_id not in _ACTIONS:
        raise KeyError(f"unknown action {action_id!r} — actions must be registered, not invented")
    return _ACTIONS[action_id]


def all_actions(domain: ActionDomain | None = None) -> list[ActionSpec]:
    """Every registered action, or only those serving one domain.

    Filtering is a view, not a second registry. `get` still resolves any
    registered id, because a plan written against one domain must not become
    unexecutable because a deployment happens to present the other.
    """
    actions = list(_ACTIONS.values())
    if domain is not None:
        actions = [a for a in actions if domain in a.domains]
    return sorted(actions, key=lambda a: a.base_risk)


def _bootstrap() -> None:
    """Baseline registry matching the risk table in docs/specs/Policy Model.md."""
    register(
        ActionSpec(
            id="read_logs",
            description="Read logs for an entity",
            base_risk=0,
            expected_post_state={},
            read_only=True,
            # The same act whichever question prompted it. A second id would
            # give the policy engine two risk scores for one thing.
            domains=BOTH,
        )
    )
    register(
        ActionSpec(
            id="read_metrics",
            description="Query metrics for an entity",
            base_risk=0,
            expected_post_state={},
        )
    )
    register(
        ActionSpec(
            id="notify_engineer",
            description="Page or notify an on-call engineer",
            base_risk=0,
            expected_post_state={},
        )
    )
    register(
        ActionSpec(
            id="create_ticket",
            description="Open a tracking ticket for the incident",
            base_risk=0,
            expected_post_state={},
        )
    )
    register(
        ActionSpec(
            id="restart_service",
            description="Restart a service or pod",
            base_risk=10,
            expected_post_state={"health": "healthy", "restarts": "stable"},
            rollback_action_id="restart_service",
        )
    )
    register(
        ActionSpec(
            id="scale_service",
            description="Change replica count for a deployment",
            base_risk=20,
            expected_post_state={"replicas": "target", "saturation": "<70%"},
            rollback_action_id="scale_service",
        )
    )
    register(
        ActionSpec(
            id="clear_cache",
            description="Flush a cache namespace",
            base_risk=30,
            expected_post_state={"cache_memory": "<70%", "hit_rate": "recovering"},
            rollback_action_id="warm_cache",
        )
    )
    register(
        ActionSpec(
            id="warm_cache",
            description="Repopulate a cache namespace",
            base_risk=10,
            expected_post_state={"hit_rate": "recovering"},
            rollback_action_id="clear_cache",
        )
    )
    register(
        ActionSpec(
            id="rollback_deployment",
            description="Roll a service back to its previous version",
            base_risk=45,
            expected_post_state={"version": "previous", "error_rate": "<1%"},
            rollback_action_id="redeploy_version",
        )
    )
    register(
        ActionSpec(
            id="redeploy_version",
            description="Deploy a specific version of a service",
            base_risk=45,
            expected_post_state={"version": "target"},
            rollback_action_id="rollback_deployment",
        )
    )
    register(
        ActionSpec(
            id="disable_deployment",
            description="Halt an in-progress deployment",
            base_risk=35,
            expected_post_state={"deployment": "halted"},
            rollback_action_id="redeploy_version",
        )
    )
    register(
        ActionSpec(
            id="modify_db_config",
            description="Change database configuration parameters",
            base_risk=65,
            expected_post_state={"config": "target", "connections": "<70%"},
            rollback_action_id="modify_db_config",
        )
    )
    # Registered so the policy layer can explicitly deny it. IAM grants this to
    # no Pashupatastra role in any environment (docs/DEPLOYMENT.md).
    register(
        ActionSpec(
            id="delete_infrastructure",
            description="Destroy an infrastructure resource",
            base_risk=100,
            expected_post_state={},
            irreversible=True,
        )
    )


SECURITY = frozenset({ActionDomain.SECURITY})
BOTH = frozenset({ActionDomain.INFRASTRUCTURE, ActionDomain.SECURITY})


def _bootstrap_security() -> None:
    """Blue-team registry — the same risk tiers, read for a security console.

    Two things differ from the infrastructure set in a way worth reading.

    **Undoing containment is not cheap.** Restoring a cache is benign, so
    `warm_cache` scores below `clear_cache`. Security inverts that: returning an
    isolated host to the network, or re-enabling an account that may still be
    compromised, is about as dangerous as the containment was. Every undo below
    is scored on its own merits rather than discounted for being a rollback.

    **Some actions have no undo, and say so.** A rotated credential is not
    un-rotated; a wiped disk is not un-wiped. They are registered anyway and
    marked irreversible so Dharma refuses them by name.
    """
    register(
        ActionSpec(
            id="query_threat_intel",
            description="Look up an indicator in threat intelligence",
            base_risk=0,
            expected_post_state={},
            read_only=True,
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="notify_analyst",
            description="Notify or page a security analyst",
            base_risk=0,
            expected_post_state={},
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="create_case",
            description="Open a case for the incident",
            base_risk=0,
            expected_post_state={},
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="require_mfa_reauth",
            description="Force re-authentication with a second factor",
            base_risk=10,
            expected_post_state={"session": "re-verified"},
            rollback_action_id="clear_mfa_requirement",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="clear_mfa_requirement",
            description="Lift a step-up authentication requirement",
            base_risk=10,
            expected_post_state={"session": "unchallenged"},
            rollback_action_id="require_mfa_reauth",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="rate_limit_account",
            description="Throttle an account's request rate",
            base_risk=15,
            expected_post_state={"request_rate": "<threshold"},
            rollback_action_id="remove_rate_limit",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="remove_rate_limit",
            description="Lift a rate limit from an account",
            base_risk=15,
            expected_post_state={"request_rate": "unthrottled"},
            rollback_action_id="rate_limit_account",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="force_password_reset",
            description="Invalidate a password and require a new one",
            base_risk=20,
            expected_post_state={"credential": "rotated"},
            # No rollback: the old password is gone. Recovery is a helpdesk
            # procedure, not an action this system can take.
            irreversible=True,
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="revoke_session",
            description="Invalidate an active session or token",
            base_risk=25,
            expected_post_state={"session": "invalid"},
            rollback_action_id="reissue_session",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="reissue_session",
            description="Allow a new session after re-authentication",
            base_risk=25,
            expected_post_state={"session": "valid"},
            rollback_action_id="revoke_session",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="quarantine_email",
            description="Isolate a message from every recipient's mailbox",
            base_risk=25,
            expected_post_state={"message": "isolated"},
            rollback_action_id="release_email",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="release_email",
            description="Return a quarantined message to its recipients",
            base_risk=25,
            expected_post_state={"message": "delivered"},
            rollback_action_id="quarantine_email",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="block_ip",
            description="Deny traffic from an address at the perimeter",
            base_risk=35,
            expected_post_state={"traffic_from_ip": "denied"},
            rollback_action_id="unblock_ip",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="unblock_ip",
            description="Allow traffic from a previously blocked address",
            base_risk=35,
            expected_post_state={"traffic_from_ip": "allowed"},
            rollback_action_id="block_ip",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="disable_account",
            description="Deactivate an account",
            base_risk=45,
            expected_post_state={"account": "inactive"},
            rollback_action_id="enable_account",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="enable_account",
            description="Reactivate a disabled account",
            base_risk=45,
            expected_post_state={"account": "active"},
            rollback_action_id="disable_account",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="isolate_host",
            description="Remove a host from the network, keeping EDR reachable",
            base_risk=55,
            expected_post_state={"network": "isolated", "edr": "reachable"},
            # The EDR path staying up is the difference between containment and
            # losing the host: a machine nobody can inspect cannot be cleared,
            # and cannot be watched while somebody decides.
            rollback_action_id="rejoin_network",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="rejoin_network",
            description="Return an isolated host to the network",
            base_risk=55,
            expected_post_state={"network": "joined"},
            rollback_action_id="isolate_host",
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="rotate_credentials",
            description="Invalidate a credential everywhere it is trusted",
            base_risk=65,
            expected_post_state={"secret": "invalidated"},
            # Everything holding the old secret breaks at once, and re-issuing
            # is not undoing.
            irreversible=True,
            domains=SECURITY,
        )
    )
    register(
        ActionSpec(
            id="wipe_host",
            description="Erase a host",
            base_risk=100,
            expected_post_state={},
            # Registered so the policy layer can deny it by name. Nothing here
            # grants it, in any environment, at any confidence — an action the
            # registry never heard of is refused for the wrong reason, and the
            # refusal reads as a missing feature rather than a decision.
            irreversible=True,
            domains=SECURITY,
        )
    )


_bootstrap()
_bootstrap_security()
