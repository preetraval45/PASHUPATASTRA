"""Pashupatastra API gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

if settings.demo_seed:
    from .graph import GraphStore, entitystore
    from .seed import seed, seed_security
    from .store import STORE

    seed(GraphStore(), entitystore())
    seed_security(entitystore(), STORE)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Pashupatastra",
        "tagline": "Observe. Reason. Act. Verify.",
        "docs": "/docs",
    }
