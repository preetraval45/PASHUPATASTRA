"""Instruction data for Kushmanda — question/answer pairs from structured sources.

Pretraining teaches the model the language; supervised fine-tuning (SFT)
teaches it to *answer*. The pairs are generated from the structured data
itself, so every answer is a fact the source states — no answer here was
written by another model:

* ATT&CK — "What is T1566?", "Which technique is 'Phishing'?", "How is T1566
  mitigated?" (from `mitigates` relationships), and "Which technique does this
  behaviour describe?" (from procedure examples).
* CWE — "What is CWE-79?".
* CISA KEV — "What is CVE-…?", "What should be done about CVE-…?".

**Held out by entity.** A technique, CWE or CVE lands wholly in training or
wholly in the test, by hash — so a test question is never about something the
model was tuned to answer.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sati.lm.corpus import ATTACK, KEV, _clean, _get, cwe_documents

USER, ASSISTANT, END = "<|user|>", "<|assistant|>", "<|end|>"


def first(text: str, sentences: int = 2, limit: int = 420) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:sentences])[:limit]


def held_out(entity: str, share: float = 0.1) -> bool:
    return int(hashlib.sha256(entity.encode()).hexdigest(), 16) % 1000 < share * 1000


def format_pair(question: str, answer: str) -> tuple[str, str]:
    """The chat template. Loss is taken on the answer part only."""
    return f"{USER} {question}\n{ASSISTANT} ", f"{answer} {END}"


def attack_pairs(cache: Path) -> list[dict]:
    bundle = json.loads(_get(ATTACK, cache))
    objects = {o["id"]: o for o in bundle["objects"]}

    def attack_id(o: dict) -> str:
        return next((r["external_id"] for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), "")

    pairs = []
    techniques = {
        o["id"]: o for o in bundle["objects"]
        if o["type"] == "attack-pattern" and not o.get("revoked") and not o.get("x_mitre_deprecated")
    }
    for o in techniques.values():
        tid, name, desc = attack_id(o), o.get("name", ""), _clean(o.get("description", ""))
        if not tid or len(desc) < 60:
            continue
        pairs.append({"entity": tid, "kind": "define", "q": f"What is MITRE ATT&CK technique {tid}?", "a": f"{tid} is {name}. {first(desc)}"})
        pairs.append({"entity": tid, "kind": "lookup", "q": f"Which ATT&CK technique ID is '{name}'?", "a": tid})

    mitigations: dict[str, list[str]] = {}
    for o in bundle["objects"]:
        if o.get("type") == "relationship" and o.get("relationship_type") == "mitigates" and not o.get("revoked"):
            src, dst = objects.get(o["source_ref"]), o["target_ref"]
            if src and dst in techniques:
                mitigations.setdefault(dst, []).append(src.get("name", ""))
        if o.get("type") == "relationship" and o.get("relationship_type") == "uses" and o["target_ref"] in techniques:
            text = _clean(o.get("description", ""))
            tech = techniques[o["target_ref"]]
            if len(text) >= 60:
                tid = attack_id(tech)
                pairs.append({"entity": tid, "kind": "classify",
                              "q": f"Which ATT&CK technique does this behaviour describe? {first(text, 2, 300)}",
                              "a": f"{tid} — {tech.get('name', '')}"})
    for tech_id, names in mitigations.items():
        tid = attack_id(techniques[tech_id])
        listed = "; ".join(sorted(set(names))[:4])
        pairs.append({"entity": tid, "kind": "mitigate", "q": f"How can {tid} ({techniques[tech_id].get('name', '')}) be mitigated?",
                      "a": f"Mitigations for {tid}: {listed}."})
    return pairs


def kev_pairs(cache: Path) -> list[dict]:
    pairs = []
    for v in json.loads(_get(KEV, cache)).get("vulnerabilities", []):
        cve = v["cveID"]
        pairs.append({"entity": cve, "kind": "define", "q": f"What is {cve}?",
                      "a": f"{v.get('vulnerabilityName', '')}. {first(v.get('shortDescription', ''))}".strip()})
        pairs.append({"entity": cve, "kind": "remediate", "q": f"What should be done about {cve}?",
                      "a": v.get("requiredAction", "").strip()})
    return pairs


def cwe_pairs(cache: Path) -> list[dict]:
    pairs = []
    for doc in cwe_documents(cache):
        header, _, body = doc["text"].partition("\n")
        pairs.append({"entity": doc["id"], "kind": "define", "q": f"What is {doc['id']}?", "a": f"{header}. {first(body)}"})
    return pairs


def build(cache: Path) -> tuple[list[dict], list[dict]]:
    pairs = [p for p in (*attack_pairs(cache), *kev_pairs(cache), *cwe_pairs(cache)) if p["a"].strip()]
    train = [p for p in pairs if not held_out(p["entity"])]
    test = [p for p in pairs if held_out(p["entity"])]
    return train, test
