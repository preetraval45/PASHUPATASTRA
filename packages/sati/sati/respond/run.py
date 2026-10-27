"""Train and test Skandamata v0: from observed behaviour to the mitigations that defend against it.

    python -m sati.respond.run --cache .cache/corpus --out results/skandamata

Skandamata is model 5 of the nine (adr/Navadurga): the protective one. In Sati
it proposes the defensive response, and Dharma still authorises it (rule 2).
It recommends; it never acts.

**Model.** A multi-label classifier written from scratch in PyTorch. A
behaviour's text becomes hashed word unigrams and bigrams (Brahmacharini's
featuriser); an `EmbeddingBag`, a hidden layer with dropout, and one logit per
ATT&CK mitigation follow. It is trained with binary cross-entropy against the
full set of right mitigations. The epoch is chosen by validation nDCG@10.

**Split.** By source, as for Brahmacharini: test behaviours are written about
groups, malware families, tools and campaigns never seen in training.

**Baselines,** on the same test behaviours:

* **Popularity:** the training set's most frequent mitigations, the same for
  everyone. Hard to beat when a few mitigations (audit, user training) apply
  to most techniques.
* **BM25 direct:** the behaviour matched against each mitigation's
  description.
* **BM25 two-hop:** the behaviour matched against technique descriptions, then
  the five nearest techniques' mitigations, weighted by match.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from sati.embed.metrics import bm25
from sati.embed.model import BUCKETS, hashed
from sati.respond import metrics
from sati.respond.data import Data, build

EPOCHS = 20
BATCH = 64


class Recommender(nn.Module):
    def __init__(self, labels: int, width: int = 256, hidden: int = 256, buckets: int = BUCKETS,
                 dropout: float = 0.3) -> None:
        super().__init__()
        self.buckets = buckets
        self.bag = nn.EmbeddingBag(buckets, width, mode="mean")
        self.head = nn.Sequential(nn.Linear(width, hidden), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden, labels))
        nn.init.normal_(self.bag.weight, std=0.05)

    def forward(self, texts: list[str]) -> torch.Tensor:
        ids, offsets = [], []
        for text in texts:
            offsets.append(len(ids))
            ids.extend(hashed(text, self.buckets))
        return self.head(self.bag(torch.tensor(ids, dtype=torch.long), torch.tensor(offsets, dtype=torch.long)))


def targets(golds: list[frozenset[int]], size: int) -> torch.Tensor:
    y = torch.zeros(len(golds), size)
    for i, g in enumerate(golds):
        y[i, list(g)] = 1.0
    return y


@torch.no_grad()
def predict(model: Recommender, texts: list[str]) -> np.ndarray:
    model.eval()
    out = np.vstack([torch.sigmoid(model(texts[i : i + 512])).numpy() for i in range(0, len(texts), 512)])
    model.train()
    return out


def linear_baseline(data: Data, queries: list[str], size: int) -> np.ndarray:
    """TF-IDF uni- and bigrams with one logistic regression per mitigation.
    Added 27 Oct after the public Kaggle notebook found it beats Skandamata on
    this split; it is reported beside the model so the comparison is honest."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier

    texts = [e.text for e in data.train]
    y = targets([e.gold for e in data.train], size).numpy().astype(int)
    keep = (y.sum(0) > 0) & (y.sum(0) < len(y))  # a label true for none or all rows cannot be fitted
    scores = np.full((len(queries), size), -1.0)
    if keep.sum() == 0:
        return scores
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2 if len(texts) > 100 else 1, sublinear_tf=True).fit(texts)
    clf = OneVsRestClassifier(LogisticRegression(max_iter=1000, C=4)).fit(vec.transform(texts), y[:, keep])
    scores[:, keep] = clf.predict_proba(vec.transform(queries)).reshape(len(queries), -1)
    return scores


def train(data: Data, epochs: int = EPOCHS) -> tuple[Recommender, list[dict]]:
    size = len(data.mitigations)
    model = Recommender(size)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    rows = list(data.train)
    best, best_state, curve = -1.0, None, []
    for epoch in range(1, epochs + 1):
        random.shuffle(rows)
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            loss = loss_fn(model([e.text for e in batch]), targets([e.gold for e in batch], size))
            opt.zero_grad()
            loss.backward()
            opt.step()
        v = metrics.evaluate(predict(model, [e.text for e in data.validation]), [e.gold for e in data.validation])
        curve.append({"epoch": epoch, "loss": round(loss.item(), 4), "val_ndcg@10": v["ndcg@10"]})
        print(f"  epoch {epoch}: loss {loss.item():.4f}  val nDCG@10 {v['ndcg@10']:.3f}")
        if v["ndcg@10"] > best:
            best, best_state = v["ndcg@10"], {k: t.clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    return model, curve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--out", type=Path, default=Path("results/skandamata"))
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()

    started = time.time()
    torch.manual_seed(7)
    random.seed(7)
    data = build(args.cache)
    size = len(data.mitigations)
    print(f"{size} mitigations; behaviours train {len(data.train)}, val {len(data.validation)}, test {len(data.test)}")

    model, curve = train(data, args.epochs)
    queries, golds = [e.text for e in data.test], [e.gold for e in data.test]
    mit_text = [f"{m.name}. {m.text}" for m in data.mitigations]
    tech_text = [t for t, _ in data.techniques]
    results_by = {
        "skandamata-v0": metrics.evaluate(predict(model, queries), golds),
        "popularity": metrics.evaluate(metrics.popularity([e.gold for e in data.train], size, len(queries)), golds),
        "bm25 direct": metrics.evaluate(bm25(queries, mit_text), golds),
        "bm25 two-hop": metrics.evaluate(
            metrics.two_hop(bm25(queries, tech_text), [g for _, g in data.techniques], size), golds),
        "tf-idf logistic regression": metrics.evaluate(linear_baseline(data, queries, size), golds),
    }
    gold_sizes = [len(g) for g in golds]

    # What it recommends for a few test behaviours, unedited.
    probs = predict(model, queries[:5])
    examples = [{
        "behaviour": e.text[:240],
        "expected": sorted(data.mitigations[m].name for m in e.gold),
        "recommended": [data.mitigations[j].name for j in np.argsort(-p)[:5]],
    } for e, p in zip(data.test[:5], probs, strict=True)]

    args.out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out / "skandamata-v0.pt")
    results = {
        "model": "sati-skandamata-v0",
        "dataset": {"name": "MITRE ATT&CK enterprise: procedure examples and mitigates relationships",
                    "mitigations": size,
                    "behaviours": {"train": len(data.train), "validation": len(data.validation), "test": len(data.test)},
                    "test_sources_unseen": len({e.source for e in data.test}),
                    "right_mitigations_per_behaviour": round(float(np.mean(gold_sizes)), 2)},
        "task": "rank every ATT&CK mitigation for an observed behaviour",
        "test": results_by,
        "best_epoch_by_validation": max(curve, key=lambda c: c["val_ndcg@10"])["epoch"],
        "curve": curve,
        "examples": examples,
        "seconds": round(time.time() - started, 1),
    }
    (args.out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, m in results_by.items():
        print(f"  {name:16} hit@1 {m['hit@1']:.3f}  recall@5 {m['recall@5']:.3f}  nDCG@10 {m['ndcg@10']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
