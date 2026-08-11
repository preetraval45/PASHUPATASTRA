"""The closed action registry.

Actions come from here, never from parsed model text (the Grounding ADR). Every entry
declares its risk, its expected post-state, and its rollback — an action without
a rollback cannot be autonomous.
"""

from __future__ import annotations

from .dharma import ActionSpec

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


def all_actions() -> list[ActionSpec]:
    return sorted(_ACTIONS.values(), key=lambda a: a.base_risk)


def _bootstrap() -> None:
    """Baseline registry matching the risk table in docs/specs/Policy Model.md."""
    register(
        ActionSpec(
            id="read_logs",
            description="Read logs for an entity",
            base_risk=0,
            expected_post_state={},
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


_bootstrap()
