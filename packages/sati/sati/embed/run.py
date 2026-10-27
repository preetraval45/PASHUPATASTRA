"""Train and test Brahmacharini v0: from observed behaviour to ATT&CK technique.

    python -m sati.embed.run --cache .cache/corpus --out results/brahmacharini

For every held-out procedure — written about a group, malware family, tool or
campaign never seen in training — rank all ATT&CK techniques and score where
the true one lands. Compared on exactly the same queries with:

* **BM25**, the standard lexical retriever;
* **HashingEmbedder**, the embedder Smriti uses today (`pashupatastra.smriti`).

Reported: Recall@1, @5, @10 and MRR. Epoch count is chosen on the validation
sources, never the test.

`--arch transformer` (Brahmacharini v1, run on Kaggle's GPU) trains v0 and the
transformer encoder in the same run, on the same split, so the two are compared
on identical queries.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

from sati.embed import data as d
from sati.embed.metrics import bm25, ranks, summarise
from sati.embed.model import Encoder, TransformerEncoder, info_nce

EPOCHS = 12
BATCH = 128


def hashing(queries: list[str], docs: list[str]) -> np.ndarray | None:
    try:
        from pashupatastra.smriti import HashingEmbedder
    except ImportError:
        return None
    emb = HashingEmbedder()
    q, k = np.array(emb.embed(queries)), np.array(emb.embed(docs))
    q /= np.linalg.norm(q, axis=1, keepdims=True) + 1e-9
    k /= np.linalg.norm(k, axis=1, keepdims=True) + 1e-9
    return q @ k.T


@torch.no_grad()
def encode(model: Encoder, texts: list[str]) -> np.ndarray:
    model.eval()
    out = torch.cat([model(texts[i : i + 512]).cpu() for i in range(0, len(texts), 512)]).numpy()
    model.train()
    return out


def fit(model, opt, epochs: int, train, val, techniques, index, tech_text, name: str):
    """Contrastive training; the epoch kept is the one best on the validation sources."""
    best_state, best_val, curve = None, -1.0, []
    train = list(train)
    for epoch in range(1, epochs + 1):
        random.shuffle(train)
        for i in range(0, len(train), BATCH):
            batch = train[i : i + BATCH]
            # One positive per technique per batch, so no in-batch "negative" is
            # secretly the same technique.
            seen, uniq = set(), []
            for p in batch:
                if p.technique not in seen:
                    seen.add(p.technique)
                    uniq.append(p)
            if len(uniq) < 2:
                continue
            q = model([p.text for p in uniq])
            k = model([techniques[index[p.technique]].text for p in uniq])
            loss = info_nce(q, k)
            opt.zero_grad()
            loss.backward()
            opt.step()
        val_scores = encode(model, [p.text for p in val]) @ encode(model, tech_text).T
        v = summarise(ranks(val_scores, [index[p.technique] for p in val]))
        curve.append({"epoch": epoch, "loss": round(loss.item(), 4), "val_mrr": v["mrr"]})
        print(f"  {name} epoch {epoch}: loss {loss.item():.3f}  val MRR {v['mrr']:.3f}")
        if v["mrr"] > best_val:
            best_val, best_state = v["mrr"], {k: t.clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    return curve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--out", type=Path, default=Path("results/brahmacharini"))
    parser.add_argument("--arch", choices=("bag", "transformer"), default="bag")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    started = time.time()
    torch.manual_seed(7)
    random.seed(7)
    techniques, procedures = d.load(args.cache)
    train, val, test = d.split_by_source(procedures)
    index = {t.stix_id: i for i, t in enumerate(techniques)}
    tech_text = [t.text for t in techniques]
    print(f"{len(techniques)} techniques; procedures train {len(train)}, val {len(val)}, test {len(test)}; "
          f"test sources {len({p.source for p in test})} never seen in training")

    model = Encoder()
    # v0 exactly as published: Adam at 2e-3, so this refactor changes none of its numbers.
    curve = fit(model, torch.optim.Adam(model.parameters(), lr=2e-3), EPOCHS, train, val, techniques, index,
                tech_text, "v0")
    v1 = v1_curve = None
    if args.arch == "transformer":
        torch.manual_seed(7)
        v1 = TransformerEncoder().to(device)
        print(f"v1: {v1.parameters_count() / 1e6:.1f}M parameters on {device}")
        v1_curve = fit(v1, torch.optim.AdamW(v1.parameters(), lr=3e-4, weight_decay=0.01), args.epochs, train, val,
                       techniques, index, tech_text, "v1")

    queries = [p.text for p in test]
    gold = [index[p.technique] for p in test]
    results_by = {"brahmacharini-v0": summarise(ranks(encode(model, queries) @ encode(model, tech_text).T, gold))}
    if v1 is not None:
        results_by["brahmacharini-v1 (transformer)"] = summarise(
            ranks(encode(v1, queries) @ encode(v1, tech_text).T, gold))
    results_by["bm25"] = summarise(ranks(bm25(queries, tech_text), gold))
    hashed = hashing(queries, tech_text)
    if hashed is not None:
        results_by["hashing-embedder (Smriti today)"] = summarise(ranks(hashed, gold))

    args.out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out / "brahmacharini-v0.pt")
    if v1 is not None:
        torch.save(v1.state_dict(), args.out / "brahmacharini-v1.pt")
    results = {
        "model": "sati-brahmacharini-v1" if v1 is not None else "sati-brahmacharini-v0",
        "v1": {"parameters": v1.parameters_count(), "device": device, "curve": v1_curve,
               "best_epoch_by_validation": max(v1_curve, key=lambda c: c["val_mrr"])["epoch"]} if v1 is not None else None,
        "dataset": {"name": "MITRE ATT&CK enterprise procedure examples", "techniques": len(techniques),
                    "procedures": {"train": len(train), "validation": len(val), "test": len(test)},
                    "test_sources_unseen": len({p.source for p in test})},
        "task": "rank all techniques for an observed behaviour",
        "test": results_by,
        "best_epoch_by_validation": max(curve, key=lambda c: c["val_mrr"])["epoch"],
        "curve": curve,
        "seconds": round(time.time() - started, 1),
    }
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for name, m in results_by.items():
        print(f"  {name:32} R@1 {m['recall@1']:.3f} R@10 {m['recall@10']:.3f} MRR {m['mrr']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
