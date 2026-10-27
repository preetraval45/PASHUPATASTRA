"""Export Skandamata for serving inside the API — no PyTorch, no NumPy.

    python -m sati.respond.export --cache .cache/corpus --out services/api/app/sati_models

The same design as the evaluated model (`run.py`), smaller so the Lambda
archive stays lean: fewer hash buckets, a narrower bag. It is trained on every
behaviour (this is the served model, not the evaluated one; the evaluated
numbers are in `models/skandamata.md`). The bag is quantised to int8 with a
scale per row. The two dense layers stay float: they are small.

Before writing, the export checks that a pure-Python forward pass ranks
mitigations exactly as PyTorch does on sample behaviours, so the API cannot
serve a different model from the one trained.

Files written:

* `skandamata.json` — config, the bag's per-row scales, both dense layers, and
  each mitigation's ATT&CK id, name and link
* `skandamata.bag`  — int8 bag rows, row-major
"""

from __future__ import annotations

import argparse
import json
import math
import random
import zlib
from pathlib import Path

import numpy as np
import torch
from torch import nn

from sati.embed.export import quantise
from sati.embed.model import WORD
from sati.respond import run
from sati.respond.data import build

SERVE_BUCKETS = 1 << 15
WIDTH = 128
HIDDEN = 128
EPOCHS = 18
SAMPLES = (
    "The group used spearphishing attachments to deliver a macro-enabled document.",
    "The malware dumped credentials from LSASS memory.",
    "The actor encrypted files on network shares and demanded a ransom.",
)


def serve_forward(meta: dict, bag: bytes, text: str) -> list[float]:
    """What the API computes: hashed n-grams → mean of int8 rows → ReLU layer → logits."""
    words = WORD.findall(text.lower())
    grams = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
    ids = [zlib.crc32(g.encode()) % meta["buckets"] for g in grams] or [0]
    width = meta["width"]
    pooled = [0.0] * width
    for i in ids:
        s = meta["bag_scale"][i]
        row = bag[i * width : (i + 1) * width]
        for j in range(width):
            v = row[j] - 256 if row[j] > 127 else row[j]
            pooled[j] += v * s
    pooled = [x / len(ids) for x in pooled]
    hidden = [max(0.0, sum(w * x for w, x in zip(r, pooled, strict=True)) + b)
              for r, b in zip(meta["w1"], meta["b1"], strict=True)]
    return [sum(w * h for w, h in zip(r, hidden, strict=True)) + b for r, b in zip(meta["w2"], meta["b2"], strict=True)]


def train(cache: Path) -> tuple[run.Recommender, list]:
    torch.manual_seed(7)
    random.seed(7)
    data = build(cache)
    rows = [*data.train, *data.validation, *data.test]
    size = len(data.mitigations)
    model = run.Recommender(size, width=WIDTH, hidden=HIDDEN, buckets=SERVE_BUCKETS)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    for epoch in range(EPOCHS):
        random.shuffle(rows)
        for i in range(0, len(rows), run.BATCH):
            batch = rows[i : i + run.BATCH]
            loss = loss_fn(model([e.text for e in batch]), run.targets([e.gold for e in batch], size))
            opt.zero_grad()
            loss.backward()
            opt.step()
        print(f"  epoch {epoch + 1}: loss {loss.item():.4f}")
    return model.eval(), data.mitigations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    model, mitigations = train(args.cache)
    q_bag, bag_scale = quantise(model.bag.weight.detach().numpy())
    first, second = model.head[0], model.head[3]
    meta = {
        "model": "sati-skandamata-serve-v0",
        "buckets": SERVE_BUCKETS, "width": WIDTH, "hidden": HIDDEN,
        "bag_scale": [round(float(s), 8) for s in bag_scale],
        "w1": [[round(float(x), 6) for x in r] for r in first.weight.detach().numpy()],
        "b1": [round(float(x), 6) for x in first.bias.detach().numpy()],
        "w2": [[round(float(x), 6) for x in r] for r in second.weight.detach().numpy()],
        "b2": [round(float(x), 6) for x in second.bias.detach().numpy()],
        "mitigations": [{"id": m.attack_id, "name": m.name,
                         "url": f"https://attack.mitre.org/mitigations/{m.attack_id}/"} for m in mitigations],
    }
    bag = q_bag.tobytes()
    with torch.no_grad():
        reference = model(list(SAMPLES)).numpy()
    for text, ref in zip(SAMPLES, reference, strict=True):
        served = serve_forward(meta, bag, text)
        top_ref, top_served = list(np.argsort(-ref)[:5]), sorted(range(len(served)), key=lambda j: -served[j])[:5]
        drift = max(abs(a - b) for a, b in zip(served, ref, strict=True))
        print(f"  parity: top-5 {'same' if top_ref == top_served else 'DIFFERS'}, max logit drift {drift:.3f}")
        # int8 rounding moves logits slightly; it must not reorder the top three.
        assert top_ref[:3] == top_served[:3] and math.isfinite(drift), "served model ranks differently from PyTorch"

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "skandamata.bag").write_bytes(bag)
    (args.out / "skandamata.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"exported: {len(mitigations)} mitigations, bag {q_bag.nbytes / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
