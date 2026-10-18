"""The Ask console's model picker is an allow-list (RP-50).

What has to hold: the list comes from server configuration only, a chat request
can name an id from it and nothing else, and choosing nothing changes nothing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.engines import buddhi


@pytest.fixture
def configure(monkeypatch):
    """Set PASHU_ variables and rebuild everything that cached the old ones."""

    def apply(**env: str) -> None:
        for name, value in env.items():
            monkeypatch.setenv(f"PASHU_{name.upper()}", value)
        get_settings.cache_clear()
        buddhi.gateway.cache_clear()
        buddhi.gateway_for.cache_clear()

    yield apply
    get_settings.cache_clear()
    buddhi.gateway.cache_clear()
    buddhi.gateway_for.cache_clear()


def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_without_a_fallback_only_the_default_is_offered(configure, monkeypatch) -> None:
    monkeypatch.delenv("PASHU_FALLBACK_BASE_URL", raising=False)
    configure(model_provider="echo")

    models = client().get("/api/v1/models").json()["models"]
    assert [m["id"] for m in models] == ["default"]
    assert models[0]["default"] is True


def test_the_fallback_box_models_are_offered_once_each(configure) -> None:
    configure(
        model_provider="failover",
        model_id="openai/gpt-oss-20b",
        fallback_base_url="https://ollama.example/v1",
        fallback_model="qwen2.5:7b",
        chat_models="mistral, llama3, qwen2.5:7b",
    )

    models = client().get("/api/v1/models").json()["models"]
    assert [m["id"] for m in models] == [
        "default",
        "ollama:qwen2.5:7b",
        "ollama:mistral",
        "ollama:llama3",
    ]
    assert "qwen2.5:7b" in models[0]["label"]


def test_a_model_not_on_the_list_is_refused_before_any_spend(configure) -> None:
    configure(model_provider="echo")

    response = client().post(
        "/api/v1/agent/chat",
        json={"incident_id": "INC-2026-0901", "message": "hi", "model": "ollama:evil"},
    )
    assert response.status_code == 422
    assert "unknown model" in response.json()["detail"]


def test_a_chosen_model_gets_its_own_gateway(configure) -> None:
    configure(
        model_provider="echo",
        fallback_base_url="https://ollama.example/v1",
        fallback_model="qwen2.5:7b",
    )

    chosen = buddhi.gateway_for("ollama:qwen2.5:7b")
    assert chosen.provider.model == "qwen2.5:7b"
    assert chosen is not buddhi.gateway()
    assert buddhi.gateway_for("ollama:qwen2.5:7b") is chosen


def test_choosing_the_default_is_the_process_gateway(configure) -> None:
    configure(model_provider="echo")
    assert buddhi.gateway_for("default") is buddhi.gateway()


def test_an_unlisted_id_raises_rather_than_building_a_provider(configure) -> None:
    configure(model_provider="echo", fallback_base_url="https://ollama.example/v1")
    with pytest.raises(KeyError):
        buddhi.gateway_for("ollama:not-configured")
