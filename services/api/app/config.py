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

    database_url: str = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"
    redis_url: str = "redis://localhost:6379/0"
    opensearch_url: str = "http://localhost:9200"
    prometheus_url: str = "http://localhost:9090"

    aws_region: str = "us-east-1"
    artifacts_bucket: str | None = None
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"

    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def live_execution_enabled(self) -> bool:
        return not self.dry_run


@lru_cache
def get_settings() -> Settings:
    return Settings()
