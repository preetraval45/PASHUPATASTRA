"""Which store is holding the data, decided once.

Three modules used to decide this separately — `store.py` for incidents,
`engines/audit.py` for the audit trail, `graph.py` for topology — each calling
`is_available()` on its own. That cost up to three connection attempts on a
cold start against a database nobody configured, and it allowed something
worse: they could disagree. An audit trail on Postgres while incidents sat in
memory would report `degraded` from one seam and `ok` from another, and
`/health` would be answering for only a third of the system.

Order of preference:

1. **DynamoDB**, when a table is configured. Chosen for the demo because its
   free allowance does not expire; RDS's dies after twelve months, at which
   point a deployment either starts costing money or starts claiming a
   durability it no longer has.
2. **Postgres**, when it is reachable. The better database for this data, and
   what an on-prem deployment would use.
3. **Neither**, and then every store falls back to memory and health says
   `degraded` — which is true, and is the point of saying it.
"""

from __future__ import annotations

from .config import get_settings

_backend: object | None = None
_resolved = False


def durable():
    """The durable store, or `None`. Resolved once per process.

    Re-checking would put a connection attempt in front of every read on a
    deployment that has no database at all.
    """
    global _backend, _resolved
    if _resolved:
        return _backend

    settings = get_settings()

    if settings.dynamo_table:
        from .dynamo import DynamoStore

        candidate = DynamoStore()
        _backend = candidate if candidate.available() else None
    else:
        from .db import PostgresStore, is_available

        _backend = PostgresStore() if is_available() else None

    _resolved = True
    return _backend


def reset() -> None:
    """Forget the decision. For tests that change configuration between cases —
    nothing in the running application should call this."""
    global _backend, _resolved
    _backend, _resolved = None, False
