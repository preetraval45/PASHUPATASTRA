"""Responses are compressed when the client accepts it, and not otherwise."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_a_large_response_is_gzipped_for_a_client_that_accepts_it() -> None:
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    assert response.json()["info"]["title"] == "Pashupatastra API", "decodes to the same document"


def test_a_client_that_does_not_accept_gzip_gets_plain_json() -> None:
    response = client.get("/openapi.json", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in response.headers


def test_a_small_response_is_left_alone() -> None:
    response = client.get("/api/v1/health", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    if len(response.content) < 1024:
        assert "content-encoding" not in response.headers
