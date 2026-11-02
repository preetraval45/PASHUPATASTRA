"""Malicious packages: read from OSV's archives, kept only when malicious and recent, and turned
into incidents that name the package, the ecosystem and what the reporter found."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.feeds import liveincidents as live

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import fetchhistory  # noqa: E402

NOW = datetime.now(UTC)
DETAILS = "\n---\n_-= Per source details. Do not edit below this line.=-_\n\n## Source: kam193 (abc)\nPackage downloads a stealer at install.\n"


def archive(entries: dict[str, dict]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, entry in entries.items():
            z.writestr(name, json.dumps(entry))
    return buffer.getvalue()


def entry(oid: str, days_ago: int, name: str, **extra) -> dict:
    return {"id": oid, "published": (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z"),
            "details": DETAILS, "affected": [{"package": {"name": name, "ecosystem": "npm"}}], **extra}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_only_recent_unwithdrawn_malicious_entries_are_kept(monkeypatch) -> None:
    payload = archive({
        "MAL-2026-1.json": entry("MAL-2026-1", 3, "evil-pkg"),
        "MAL-2024-9.json": entry("MAL-2024-9", 800, "old-pkg"),
        "MAL-2026-2.json": entry("MAL-2026-2", 3, "gone-pkg", withdrawn="2026-11-01T00:00:00Z"),
        "GHSA-xxxx.json": entry("GHSA-xxxx", 3, "a-vulnerability"),
    })
    monkeypatch.setattr(fetchhistory, "ECOSYSTEMS", ("npm",))
    monkeypatch.setattr(fetchhistory.urllib.request, "urlopen", lambda *a, **k: Response(payload))
    rows = fetchhistory.osv_malicious(days=365)
    assert [r["labels"]["package"] for r in rows] == ["evil-pkg"]
    assert rows[0]["labels"]["summary"] == "Package downloads a stealer at install."
    assert rows[0]["provenance"]["url"] == "https://osv.dev/vulnerability/MAL-2026-1"


def test_a_recent_package_is_live_and_an_older_one_is_past() -> None:
    def row(oid: str, days_ago: int) -> dict:
        return {"id": f"hist-osv-{oid}", "source": "osv-malicious",
                "occurred_at": (NOW - timedelta(days=days_ago)).isoformat(),
                "entity_key": f"indicator:package:npm/{oid}",
                "labels": {"package": "evil-pkg", "ecosystem": "npm", "osv": oid, "summary": "Steals tokens."},
                "provenance": {"url": f"https://osv.dev/vulnerability/{oid}"}}

    rows = [row("MAL-2026-1", 2), row("MAL-2026-0", 30)]
    current = {i.id for i in live._packages(rows, NOW)}
    assert current == {"LIVE-PKG-MAL-2026-1"}
    past = live._packages(rows, NOW, days=None, prefix="PAST-")
    incident = next(i for i in past if i.id == "PAST-PKG-MAL-2026-0")
    assert incident.hypotheses[0].statement.startswith("evil-pkg on npm was published with malicious code: Steals tokens.")
    assert incident.sources[0].url.startswith("https://osv.dev/")
