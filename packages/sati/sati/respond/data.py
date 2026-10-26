"""Skandamata's data: observed behaviour → the mitigations that defend against it.

Everything comes from MITRE ATT&CK (enterprise), royalty-free with
attribution:

* **Mitigations:** the `course-of-action` objects (M1xxx), each with a name
  and a description.
* **Ground truth:** ATT&CK's own `mitigates` relationships. The right
  mitigations for a behaviour are the ones ATT&CK links to the technique the
  behaviour was filed under. A sub-technique with none of its own inherits its
  parent technique's.
* **Behaviours:** procedure examples, written about a named group, malware
  family, tool or campaign (`sati.embed.data.load`). They are split by that
  source, as for Brahmacharini, so test behaviours describe attackers never
  seen in training.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sati.embed.data import clean, load, split_by_source
from sati.lm.corpus import ATTACK, _get


@dataclass(frozen=True)
class Mitigation:
    stix_id: str
    attack_id: str
    name: str
    text: str


@dataclass(frozen=True)
class Example:
    source: str
    text: str
    gold: frozenset[int]
    """Indices into the mitigation list."""


def mitigations(bundle: dict) -> tuple[list[Mitigation], dict[str, set[str]]]:
    """The live mitigations, and technique STIX id → the mitigation ids that
    mitigate it, with sub-techniques inheriting from their parent when they
    have none of their own."""
    def live(o: dict) -> bool:
        return not o.get("revoked") and not o.get("x_mitre_deprecated")

    items = []
    for o in bundle["objects"]:
        if o["type"] == "course-of-action" and live(o):
            attack_id = next((r["external_id"] for r in o.get("external_references", [])
                              if r.get("source_name") == "mitre-attack"), "")
            if attack_id.startswith("M"):
                items.append(Mitigation(o["id"], attack_id, o.get("name", ""), clean(o.get("description", ""))))
    known = {m.stix_id for m in items}
    by_technique: dict[str, set[str]] = {}
    parent: dict[str, str] = {}
    for o in bundle["objects"]:
        if o["type"] != "relationship" or not live(o):
            continue
        if o.get("relationship_type") == "mitigates" and o["source_ref"] in known:
            by_technique.setdefault(o["target_ref"], set()).add(o["source_ref"])
        if o.get("relationship_type") == "subtechnique-of":
            parent[o["source_ref"]] = o["target_ref"]
    for child, up in parent.items():
        if not by_technique.get(child) and by_technique.get(up):
            by_technique[child] = set(by_technique[up])
    return items, by_technique


@dataclass
class Data:
    mitigations: list[Mitigation]
    train: list[Example]
    validation: list[Example]
    test: list[Example]
    techniques: list[tuple[str, frozenset[int]]]
    """Technique text and its mitigation indices, for the two-hop baseline."""


def build(cache: Path) -> Data:
    """Mitigations, train / validation / test examples split by source, and
    every technique with its mitigations."""
    bundle = json.loads(_get(ATTACK, cache))
    items, by_technique = mitigations(bundle)
    index = {m.stix_id: i for i, m in enumerate(items)}
    techniques, procedures = load(cache)
    parts = split_by_source(procedures)

    def examples(ps) -> list[Example]:
        out = []
        for p in ps:
            gold = frozenset(index[m] for m in by_technique.get(p.technique, ()))
            if gold:
                out.append(Example(p.source, p.text, gold))
        return out

    with_mitigations = [(t.text, frozenset(index[m] for m in by_technique.get(t.stix_id, ())))
                        for t in techniques if by_technique.get(t.stix_id)]
    return Data(items, examples(parts[0]), examples(parts[1]), examples(parts[2]), with_mitigations)
