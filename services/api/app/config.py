"""Runtime configuration.

Credentials are never read from literals or committed files. On AWS they come
from Secrets Manager via IRSA; locally from a gitignored .env (see .env.example).
"""

from __future__ import annotations

from functools import lru_cache

from pashupatastra import Environment
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

    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def live_execution_enabled(self) -> bool:
        """Both gates, and the environment must be named explicitly.

        `not dry_run` alone is not enough — see `live_environments`.
        """
        return not self.dry_run and self.environment in self.live_environments


@lru_cache
def get_settings() -> Settings:
    return Settings()
