"""Verification — observational, never model-judged (the Grounding ADR).

Compares the expected post-state an action declared *before* execution against
telemetry observed after it. Failure triggers rollback and escalation.
"""

from __future__ import annotations

from datetime import datetime

from pashupatastra import Verification, VerificationCheck

from .audit import AUDIT, AuditKind, AuditRecord


def build_checks(expected_post_state: dict[str, str]) -> list[VerificationCheck]:
    return [VerificationCheck(name=k, expected=v) for k, v in expected_post_state.items()]


def observe(
    verification: Verification,
    observed: dict[str, str],
    incident_ref: str | None = None,
    actor: str = "agent:orchestrator",
) -> Verification:
    """Fill in observed values and grade each check.

    A check with no observation is a failure, not a pass. Missing telemetry means
    the system does not know whether it worked, and "don't know" must never be
    recorded as success.
    """
    for check in verification.checks:
        check.observed = observed.get(check.name)
        check.passed = check.observed is not None and _matches(check.expected, check.observed)

    verification.completed_at = datetime.now().astimezone()
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.VERIFICATION,
            actor=actor,
            incident_ref=incident_ref,
            summary=f"verification {'passed' if verification.passed else 'failed'}",
            detail={"checks": [c.model_dump(mode="json") for c in verification.checks]},
        )
    )
    return verification


def _matches(expected: str, observed: str) -> bool:
    """Compare an expected-state expression against an observed value.

    Supports the threshold forms used in the action registry ("<70%", ">99%") and
    falls back to equality.
    """
    expected, observed = expected.strip(), observed.strip()
    for op in ("<=", ">=", "<", ">"):
        if expected.startswith(op):
            try:
                threshold = float(expected[len(op) :].rstrip("%"))
                value = float(observed.rstrip("%"))
            except ValueError:
                return False
            return {
                "<": value < threshold,
                ">": value > threshold,
                "<=": value <= threshold,
                ">=": value >= threshold,
            }[op]
    return expected.lower() == observed.lower()
