"""The served knowledge base: every passage can be cited."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("torch")
from sati.embed import export  # noqa: E402

LONG = "Use a language or compiler that performs automatic bounds checking on every buffer it writes."


def test_capec_mitigations_are_filed_under_their_attack_pattern_and_uncitable_ones_dropped(monkeypatch):
    capec = {"objects": [
        {"type": "attack-pattern", "id": "attack-pattern--1", "name": "Buffer Overflow", "description": LONG,
         "external_references": [{"external_id": "CAPEC-10", "url": "https://capec.mitre.org/data/definitions/10.html"}]},
        {"type": "course-of-action", "id": "course-of-action--a", "name": "coa-10-0", "description": LONG},
        {"type": "course-of-action", "id": "course-of-action--b", "name": "coa-99-0", "description": LONG},
    ]}
    monkeypatch.setattr(export, "_get", lambda url, cache: json.dumps(
        capec if url == export.CAPEC else {"objects": [], "vulnerabilities": []}))
    out = {p["id"]: p for p in export.passages(None)}
    assert out["CAPEC-10 mitigation 1"]["title"] == "Mitigation for Buffer Overflow"
    assert out["CAPEC-10 mitigation 1"]["url"].endswith("/10.html")
    assert all(p["url"] for p in out.values()) and len(out) == 2  # coa-99 has no pattern to cite
