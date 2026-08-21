"""Pashupatastra API gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pashupatastra.dharma import ActionDomain

from .api.routes import router
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="Pashupatastra API",
    description=(
        "Autonomous intelligence for complex systems. "
        "Observe → Reason → Act → Verify, under policy-bounded autonomy."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


def _seed_demo() -> None:
    """Load the scripted scenarios, once.

    **Idempotent against a durable store.** In memory, re-seeding on every start
    was harmless — the process began with nothing. Against a table that survives
    a restart, every cold start would append the same audit trail again until
    the page was a wall of duplicates, and Lambda cold-starts often.

    The marker carries a version, so a deployment whose scenarios have changed
    shape re-seeds rather than serving half of each.
    """
    from .graph import GraphStore, entitystore
    from .seed import seed, seed_security
    from .store import STORE

    graph, store = GraphStore(), entitystore()

    seeded = getattr(store, "seeded", None)
    if seeded is not None and seeded():
        return

    if settings.action_domain is not ActionDomain.SECURITY:
        # The labelled corpus is infrastructure telemetry. On a security console
        # it would put `checkout-api` on the map beside a compromised account —
        # the same theme-over-something-else problem as the demo incident.
        seed(graph, store)

    written = seed_security(graph, store, STORE)

    mark = getattr(store, "mark_seeded", None)
    if mark is not None:
        mark(detail=written)


if settings.demo_seed:
    _seed_demo()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Pashupatastra",
        "tagline": "Observe. Reason. Act. Verify.",
        "docs": "/docs",
    }
