"""Constrained decoding for Kushmanda (RP-44): answers that must parse, and IDs that must exist.

Kushmanda v2 writes free-text answers well but copies identifiers badly:
exact match 0.528 on "Which technique ID is …?" against 0.962 for word overlap.
A wrong ID is the one output a reader cannot catch by reading, because it looks
exactly like a right one.

So for a question whose answer is an identifier, decoding is **constrained to
the identifiers present in the passages it was given**:

* At each step, only tokens that keep the output a prefix of some identifier
  in the context are allowed. The model still chooses which identifier,
  through its own scores.
* Once an identifier is complete, the citation is the passage that contains
  it, `[n]`. Grounding then holds by construction, not by hope.
* If the context holds no identifier, the answer is the abstention.

Every output therefore parses, and every identifier is one the context
contains (RP-44's done-when: 100% of outputs valid). Whether the *right*
identifier is chosen is measured, not assumed (`constrained_eval.py`).

Works with any `next_scores(ids) -> scores` callable: PyTorch on Kaggle, or
the numpy engine (`sati.lm.infer`) in the API.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

import numpy as np

from sati.lm.sft import ABSTAIN

ID = re.compile(r"\b(T\d{4}(?:\.\d{3})?|CVE-\d{4}-\d{4,}|CWE-\d+)\b")


def identifiers(context: Sequence[str]) -> list[tuple[str, int]]:
    """(identifier, 1-based passage index) for each distinct identifier, in order of appearance."""
    seen: dict[str, int] = {}
    for i, passage in enumerate(context, start=1):
        for match in ID.findall(passage):
            seen.setdefault(match, i)
    return list(seen.items())


def constrained_id(next_scores: Callable[[list[int]], np.ndarray], decode: Callable[[list[int]], str],
                   prompt: list[int], context: Sequence[str], max_new: int = 12, top_k: int = 64) -> str:
    """Decode one identifier from those in `context`, then cite its passage.

    Greedy over the model's scores, restricted at each step to the `top_k`
    best tokens that keep the text a prefix of an allowed identifier. Stops
    when the text is a complete identifier and the model's best allowed next
    token would not extend it into a longer one."""
    allowed = identifiers(context)
    if not allowed:
        return ABSTAIN
    names = [name for name, _ in allowed]
    out: list[int] = []
    text = ""
    for _ in range(max_new):
        scores = next_scores(prompt + out)
        chosen = None
        for token in np.argsort(-scores)[:top_k]:
            candidate = decode([*out, int(token)]).strip()
            if candidate and any(name.startswith(candidate) for name in names):
                chosen, text = int(token), candidate
                break
        if chosen is None:
            break
        out.append(chosen)
        if text in names and not any(name != text and name.startswith(text) for name in names):
            break
    if text not in names:
        # The model's choices never completed an identifier: take the complete
        # one its prefix points to, or the first in the context.
        text = next((name for name in names if name.startswith(text)), names[0]) if text else names[0]
    index = dict(allowed)[text]
    return f"{text} [{index}]"
