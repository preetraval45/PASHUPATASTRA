"""Brahmacharini's data: real attacker behaviour, paired with the technique it is.

MITRE ATT&CK records *procedure examples* — how a named group, malware family,
tool or campaign actually used a technique, written by analysts from public
reporting ("Shamoon obtains the system time and will only activate if…"). Each
one links a behaviour description to its technique. That is exactly the
recall task Sati needs: given what was observed, which known behaviour is it?

**Split by source, not by example.** All of one group's procedures land on one
side, so the test asks how well the model reads the behaviour of attackers it
never saw — not whether it remembers a group's phrasing.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sati.lm.corpus import ATTACK, _get

LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
CITATION = re.compile(r"\(Citation: [^)]*\)")


def clean(text: str) -> str:
    text = LINK.sub(r"\1", text)
    text = CITATION.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Technique:
    stix_id: str
    attack_id: str
    text: str


@dataclass(frozen=True)
class Procedure:
    source: str
    technique: str
    """The technique's STIX id."""
    text: str


def load(cache: Path) -> tuple[list[Technique], list[Procedure]]:
    bundle = json.loads(_get(ATTACK, cache))
    objects = {o["id"]: o for o in bundle["objects"]}

    def live(o: dict) -> bool:
        return not o.get("revoked") and not o.get("x_mitre_deprecated")

    techniques = []
    for o in bundle["objects"]:
        if o["type"] == "attack-pattern" and live(o):
            attack_id = next((r["external_id"] for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), "")
            techniques.append(Technique(o["id"], attack_id, clean(f"{o.get('name', '')}. {o.get('description', '')}")))
    known = {t.stix_id for t in techniques}

    procedures = []
    for o in bundle["objects"]:
        if o["type"] != "relationship" or o.get("relationship_type") != "uses" or not live(o):
            continue
        source, target = objects.get(o["source_ref"]), o["target_ref"]
        if not source or source["type"] not in ("intrusion-set", "malware", "tool", "campaign") or target not in known:
            continue
        text = clean(o.get("description", ""))
        if len(text) >= 30:
            procedures.append(Procedure(o["source_ref"], target, text))
    return techniques, procedures


def split_by_source(procedures: list[Procedure]) -> tuple[list[Procedure], list[Procedure], list[Procedure]]:
    """80 / 10 / 10 by source, decided by a hash so it is stable everywhere."""
    parts: tuple[list[Procedure], list[Procedure], list[Procedure]] = ([], [], [])
    for p in procedures:
        bucket = int(hashlib.sha256(p.source.encode()).hexdigest(), 16) % 10
        parts[0 if bucket < 8 else 1 if bucket == 8 else 2].append(p)
    return parts
