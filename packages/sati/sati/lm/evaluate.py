"""Scoring Kushmanda's grounded answers, against baselines on the same questions.

Each held-out question comes with three passages (`sft.ground`). What is
measured:

* **Exact match.** Lookups and behaviour classification have one right
  technique ID.
* **Citation accuracy.** The answer cites the passage that holds its answer.
  This is what makes an answer checkable.
* **ROUGE-L F1** for free-text answers (definitions, mitigations, required
  actions) against the source's own wording (Lin, 2004).
* **Copy precision.** The share of the answer's word 4-grams found in the
  context. A grounded answer is mostly copied or composed from its passages;
  a low score means the model is writing from memory, which rule 1 forbids.
* **Abstention.** When no passage answers the question, the answer must say so;
  when one does, it must not. Both rates are reported.

Two baselines are scored the same way:

* **Lexical:** cite the passage sharing the most words with the question, and
  answer with that passage's first ID, or with its text. No learning, and a
  fair bar for a model that reads.
* **Chance:** a uniform pick among the passages.
"""

from __future__ import annotations

import random
import re

from sati.lm.sft import ABSTAIN

WORD = re.compile(r"[a-z0-9][a-z0-9\-\.]*")
ID = re.compile(r"\b(T\d{4}(?:\.\d{3})?|CVE-\d{4}-\d{4,}|CWE-\d+)\b")
CITE = re.compile(r"\[(\d)\]\s*$")
STOP = frozenset("a an and are as at be by does for from how in is it of on or that the this to was what which with".split())


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def parse(answer: str) -> tuple[str, int | None, bool]:
    """`(body, cited passage or None, abstained)`."""
    text = answer.strip()
    match = CITE.search(text)
    cite = int(match.group(1)) if match else None
    body = CITE.sub("", text).strip()
    return body, cite, body.rstrip(".").lower() == ABSTAIN.rstrip(".").lower()


def rouge_l(reference: str, hypothesis: str) -> float:
    ref, hyp = words(reference), words(hypothesis)
    if not ref or not hyp:
        return 0.0
    previous = [0] * (len(hyp) + 1)
    for r in ref:
        current = [0]
        for j, h in enumerate(hyp, 1):
            current.append(previous[j - 1] + 1 if r == h else max(previous[j], current[j - 1]))
        previous = current
    lcs = previous[-1]
    if lcs == 0:
        return 0.0
    precision, recall = lcs / len(hyp), lcs / len(ref)
    return 2 * precision * recall / (precision + recall)


def copy_precision(answer: str, context: list[str], n: int = 4) -> float:
    tokens = words(answer)
    if not tokens:
        return 0.0
    if len(tokens) < n:
        source = set(words(" ".join(context)))
        return sum(t in source for t in tokens) / len(tokens)
    grams = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    source_tokens = words(" ".join(context))
    source = {tuple(source_tokens[i : i + n]) for i in range(len(source_tokens) - n + 1)}
    return sum(g in source for g in grams) / len(grams)


def first_id(text: str) -> str:
    match = ID.search(text)
    return match.group(1) if match else ""


def lexical(pair: dict) -> str:
    """The no-learning baseline's answer, in the model's format."""
    asked = set(words(pair["q"])) - STOP
    scores = [len(asked & set(words(c))) for c in pair["context"]]
    best = max(range(len(scores)), key=lambda i: scores[i])
    chosen = pair["context"][best]
    body = first_id(chosen) if pair["kind"] in ("lookup", "classify") else chosen
    return f"{body} [{best + 1}]"


def chance(pair: dict, rng: random.Random) -> str:
    pick = rng.randrange(len(pair["context"]))
    chosen = pair["context"][pick]
    body = first_id(chosen) if pair["kind"] in ("lookup", "classify") else chosen
    return f"{body} [{pick + 1}]"


def score(pairs: list[dict], answers: list[str]) -> dict[str, dict]:
    """Per question kind: exact match (ID kinds), ROUGE-L and copy precision
    (text kinds), and citation accuracy, all on answerable questions. Plus
    abstention on unanswerable ones and false abstention on answerable ones."""
    rows: dict[str, dict[str, list[float]]] = {}
    for pair, answer in zip(pairs, answers, strict=True):
        body, cite, abstained = parse(answer)
        if not pair["answerable"]:
            rows.setdefault("unanswerable", {}).setdefault("abstained", []).append(float(abstained))
            continue
        row = rows.setdefault(pair["kind"], {})
        row.setdefault("cited_right_passage", []).append(float(cite == pair["cite"]))
        row.setdefault("false_abstention", []).append(float(abstained))
        reference, _, _ = parse(pair["a"])
        if pair["kind"] in ("lookup", "classify"):
            row.setdefault("exact_match", []).append(float(first_id(body) == first_id(reference)))
        else:
            row.setdefault("rouge_l", []).append(rouge_l(reference, body))
            row.setdefault("copy_precision", []).append(copy_precision(body, pair["context"]))
    return {
        kind: {**{m: round(sum(v) / len(v), 4) for m, v in metrics.items()}, "n": len(next(iter(metrics.values())))}
        for kind, metrics in sorted(rows.items())
    }
