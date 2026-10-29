"""Brahmacharini's TF-IDF classifier, served beside its encoder and fused with it.

On the held-out ATT&CK split the served encoder alone ranks the right technique
first for 0.557 of behaviours, and fused with this classifier for 0.650
(docs/research/models/brahmacharini.md, "served design" rows). The classifier
is exported by `sati.embed.export` as plain JSON: the full vocabulary with its
idf, and for each technique its 400 largest weights at int8. This module scores
it in pure Python, exactly as scikit-learn's TfidfVectorizer (word uni- and
bigrams, sublinear tf, L2 norm) and a softmax over the pruned weights would;
`parity` in the file pins that, and `testtechniqueclassifier.py` checks it.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "sati_models"
TOKEN = re.compile(r"(?u)\b\w\w+\b")  # scikit-learn's default token pattern


class TechniqueClassifier:
    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.fusion_weight: float = data["fusion_weight"]
        self.column = {term: i for i, term in enumerate(data["terms"])}
        self.idf: list[float] = data["idf"]
        self.ids = [c["id"] for c in data["classes"]]
        self.bias = [c["bias"] for c in data["classes"]]
        # Inverted: feature → [(class, weight)], so a query touches only its own features.
        self.postings: dict[int, list[tuple[int, float]]] = {}
        for k, c in enumerate(data["classes"]):
            for f, w in zip(c["features"], c["weights"], strict=True):
                self.postings.setdefault(f, []).append((k, w * c["scale"]))
        self.parity = data.get("parity", [])

    def features(self, text: str) -> dict[int, float]:
        words = TOKEN.findall(text.lower())
        grams = Counter(words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)])
        x = {self.column[g]: (1 + math.log(n)) * self.idf[self.column[g]] for g, n in grams.items() if g in self.column}
        norm = math.sqrt(sum(v * v for v in x.values())) or 1.0
        return {f: v / norm for f, v in x.items()}

    def probabilities(self, text: str) -> dict[str, float]:
        logits = list(self.bias)
        for f, v in self.features(text).items():
            for k, w in self.postings.get(f, ()):
                logits[k] += w * v
        top = max(logits)
        exp = [math.exp(z - top) for z in logits]
        total = sum(exp)
        return {technique: e / total for technique, e in zip(self.ids, exp, strict=True)}


def standardise(scores: dict[str, float], keys: list[str]) -> dict[str, float]:
    """Per-query z-scores over `keys`, as in training; a key a scorer cannot rank goes just below its lowest."""
    present = [scores[k] for k in keys if k in scores]
    low = (min(present) - 1e-6) if present else 0.0
    values = [scores.get(k, low) for k in keys]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) + 1e-9
    return {k: (v - mean) / sd for k, v in zip(keys, values, strict=True)}


def fuse(cosines: dict[str, float], probabilities: dict[str, float], weight: float) -> list[tuple[float, str]]:
    """Encoder and classifier, z-scored over the encoder's techniques and weighted as validation chose."""
    keys = list(cosines)
    a, b = standardise(cosines, keys), standardise(probabilities, keys)
    return sorted(((weight * a[k] + (1 - weight) * b[k], k) for k in keys), reverse=True)


def available() -> bool:
    return (FOLDER / "technique_classifier.json").exists()


@lru_cache
def served() -> TechniqueClassifier:
    return TechniqueClassifier(FOLDER / "technique_classifier.json")
