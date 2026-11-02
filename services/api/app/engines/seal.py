"""Verdict seals — a verdict is authority only if Dharma, in this service, issued it.

Every route that acts on a verdict takes it from the request body: `/actions/execute`,
`/actions/remediate`, `/policy/approve` and `/policy/deny`. Without a seal, a caller could write
`"tier": "autonomous"` into the JSON and execute anything, and the audit trail would record an
execution no policy evaluation authorised — exactly the path rule 2 forbids.

So the service signs the fields that carry authority whenever Dharma issues a verdict, and again
whenever an approval or denial changes it, and refuses any verdict whose signature does not match.
Display-only fields (`adjustments`, `tier_reasons`) are left out: older dashboards drop them, and
they change nothing about what may run. A preview verdict is never sealed, so it can be shown but
never acted on.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from pashupatastra import PolicyViolation, Verdict

SEALED = (
    "action_id",
    "incident_ref",
    "base_risk",
    "effective_risk",
    "tier",
    "required_approvers",
    "granted_by",
    "granted_at",
    "expires_at",
    "constraints",
    "denial_reason",
)


def _key() -> bytes:
    # Derived from the session-signing key rather than equal to it, so a session token can never
    # pass as a seal or the reverse. Imported here, not at module load: the accounts store is
    # created on first use.
    from ..accounts import _signing_key

    return hmac.new(_signing_key(), b"pashupatastra verdict seal v1", hashlib.sha256).digest()


def _digest(verdict: Verdict) -> str:
    fields = verdict.model_dump(mode="json", include=set(SEALED))
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def seal(verdict: Verdict) -> Verdict:
    """Sign a verdict this service has just issued or changed. Returns the same object."""
    verdict.seal = _digest(verdict)
    return verdict


def is_sealed(verdict: Verdict) -> bool:
    return verdict.seal is not None and hmac.compare_digest(verdict.seal, _digest(verdict))


def require_seal(verdict: Verdict | None) -> Verdict | None:
    """Refuse a verdict this service did not issue, or one changed since it was issued.

    `None` passes through untouched, so `require_verdict` still reports a missing verdict in its
    own words.
    """
    if verdict is not None and not is_sealed(verdict):
        raise PolicyViolation(
            f"verdict for {verdict.action_id} was not issued by this service's policy engine, "
            "or was changed after it was; obtain one from /policy/evaluate"
        )
    return verdict
