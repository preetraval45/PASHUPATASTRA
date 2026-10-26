"""Instruction data for Kushmanda: grounded question/answer pairs from structured sources.

Pretraining teaches the model the language. Supervised fine-tuning (SFT) teaches
it to *answer*, and since v2 it learns to answer **from the passages it is
given**, never from memory. That is the only role engineering rule 1 allows a
language model: "The LLM is never the source of truth."

Each question comes with three numbered passages. One holds the answer; the
other two are distractors of the same kind. The answer ends by citing the
passage it came from (`[2]`). In about one question in ten, the passage with
the answer is removed. The right reply then is to say so (`ABSTAIN`), not to
guess. In Sati, the passages come from Brahmacharini's retrieval, so the
citation points at a real source.

v1 asked the model to recall facts about entities it was never tuned on, with
no context. It scored zero. That was a test of memory, which a 34M-parameter
model trained on 1M tokens cannot have, not of answering.

Every answer is a fact its source states; no answer here was written by
another model:

* ATT&CK: define a technique, look up its ID by name, list its mitigations, and
  classify a described behaviour (a procedure example) among candidate
  techniques.
* CWE: define a weakness.
* CISA KEV: define a CVE, and say what must be done about it.

**Held out by entity.** A technique, CWE or CVE lands wholly in training or
wholly in the test, decided by hash. Distractors come from the same side.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

from sati.lm.corpus import ATTACK, KEV, _clean, _get, cwe_documents

USER, ASSISTANT, END = "<|user|>", "<|assistant|>", "<|end|>"
ABSTAIN = "The context does not answer this."
PASSAGES = 3
UNANSWERABLE = 0.1


def first(text: str, sentences: int = 2, limit: int = 420) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:sentences])[:limit]


def held_out(entity: str, share: float = 0.1) -> bool:
    return int(hashlib.sha256(entity.encode()).hexdigest(), 16) % 1000 < share * 1000


def format_pair(question: str, answer: str, context: list[str] | None = None) -> tuple[str, str]:
    """The chat template. Loss is taken on the answer part only."""
    if context:
        numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(context, 1))
        question = f"Context:\n{numbered}\nQuestion: {question}"
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
    passage: dict[str, str] = {}
    for o in techniques.values():
        tid, name, desc = attack_id(o), o.get("name", ""), _clean(o.get("description", ""))
        if not tid or len(desc) < 60:
            continue
        passage[o["id"]] = f"{tid} {name}: {first(desc, 3, 450)}"
        common = {"entity": tid, "pool": "technique", "passage": passage[o["id"]]}
        pairs.append({**common, "kind": "define", "q": f"What is MITRE ATT&CK technique {tid}?",
                      "a": f"{tid} is {name}. {first(desc, 1, 250)}"})
        pairs.append({**common, "kind": "lookup", "q": f"Which ATT&CK technique ID is '{name}'?", "a": tid})

    mitigations: dict[str, list[str]] = {}
    for o in bundle["objects"]:
        if o.get("type") == "relationship" and o.get("relationship_type") == "mitigates" and not o.get("revoked"):
            src, dst = objects.get(o["source_ref"]), o["target_ref"]
            if src and dst in techniques:
                mitigations.setdefault(dst, []).append(src.get("name", ""))
        if o.get("type") == "relationship" and o.get("relationship_type") == "uses" and o["target_ref"] in passage:
            text = _clean(o.get("description", ""))
            tech = techniques[o["target_ref"]]
            if len(text) >= 60:
                tid = attack_id(tech)
                pairs.append({"entity": tid, "pool": "technique", "passage": passage[o["target_ref"]], "kind": "classify",
                              "q": f"Which ATT&CK technique does this behaviour describe? {first(text, 2, 300)}",
                              "a": f"{tid} — {tech.get('name', '')}"})
    for tech_id, names in mitigations.items():
        if tech_id not in passage:
            continue
        tid, name = attack_id(techniques[tech_id]), techniques[tech_id].get("name", "")
        listed = "; ".join(sorted(set(names))[:4])
        pairs.append({"entity": tid, "pool": "mitigation", "kind": "mitigate",
                      "passage": f"{tid} {name} is mitigated by: {listed}.",
                      "q": f"How can {tid} ({name}) be mitigated?", "a": f"Mitigations for {tid}: {listed}."})
    return pairs


def kev_pairs(cache: Path) -> list[dict]:
    pairs = []
    for v in json.loads(_get(KEV, cache)).get("vulnerabilities", []):
        cve, name = v["cveID"], v.get("vulnerabilityName", "")
        description, action = first(v.get("shortDescription", ""), 2, 300), v.get("requiredAction", "").strip()
        common = {"entity": cve, "pool": "kev",
                  "passage": f"{cve} {name}. {description} Required action: {action}"}
        pairs.append({**common, "kind": "define", "q": f"What is {cve}?", "a": f"{name}. {first(description, 1, 250)}".strip()})
        pairs.append({**common, "kind": "remediate", "q": f"What should be done about {cve}?", "a": action})
    return pairs


def cwe_pairs(cache: Path) -> list[dict]:
    pairs = []
    for doc in cwe_documents(cache):
        header, _, body = doc["text"].partition("\n")
        pairs.append({"entity": doc["id"], "pool": "cwe", "kind": "define", "passage": f"{header}: {first(body, 3, 450)}",
                      "q": f"What is {doc['id']}?", "a": f"{header}. {first(body, 1, 250)}"})
    return pairs


def ground(pairs: list[dict], seed: int = 7) -> list[dict]:
    """Give every pair its numbered context: the passage holding the answer plus
    distractors from the same pool and the same side of the split, in a random
    order. About UNANSWERABLE of them lose the answer's passage and must abstain."""
    pools: dict[str, list[str]] = {}
    for p in pairs:
        pools.setdefault(p["pool"], []).append(p["passage"])
    pools = {k: sorted(set(v)) for k, v in pools.items()}
    out = []
    for p in pairs:
        rng = random.Random(f"{seed}:{p['kind']}:{p['q']}")
        others = [x for x in rng.sample(pools[p["pool"]], min(len(pools[p["pool"]]), PASSAGES + 2)) if x != p["passage"]]
        if len(others) < PASSAGES:
            continue
        if rng.random() < UNANSWERABLE:
            out.append({**p, "answerable": False, "context": others[:PASSAGES], "cite": None, "a": ABSTAIN})
            continue
        context = others[: PASSAGES - 1]
        cite = rng.randrange(PASSAGES)
        context.insert(cite, p["passage"])
        out.append({**p, "answerable": True, "context": context, "cite": cite + 1, "a": f"{p['a']} [{cite + 1}]"})
    return out


def build(cache: Path) -> tuple[list[dict], list[dict]]:
    pairs = [p for p in (*attack_pairs(cache), *kev_pairs(cache), *cwe_pairs(cache)) if p["a"].strip()]
    train = ground([p for p in pairs if not held_out(p["entity"])])
    test = ground([p for p in pairs if held_out(p["entity"])])
    return train, test
