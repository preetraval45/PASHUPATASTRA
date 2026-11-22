"""Brahmacharini's passage ranker: which passage of the fetched web pages answers the question.

    python -m sati.webqa.run --cache ../../.cache/webqa --out ../../results/brahmacharini-ranker \
        --export ../../services/api/app/sati_models

Data: Natural Questions (open), real search questions with short answers, CC BY-SA 3.0. Each question
is put through the served pipeline (`pashupatastra.webread`: Wikipedia, passages, features), and a
passage is relevant when it contains a gold answer. LightGBM lambdarank learns the ordering.

Declared before any result: train on NQ-open train questions, test on NQ-open validation questions
(a separate set by construction). The metric is answer@1, the share of ALL test questions whose
top-ranked passage contains a gold answer, so questions retrieval could not answer count as misses.
Compared on the same questions against the hand-set score (`webread.heuristic`) and the source's own
order. The ranker is exported for serving only if it beats the hand-set score on answer@1.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import string
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pashupatastra import trees, webread

NQ = "https://huggingface.co/api/datasets/google-research-datasets/nq_open/parquet/nq_open/{split}/0.parquet"
ROOT = Path(__file__).resolve().parents[4]
PARAMS = {"objective": "lambdarank", "metric": "ndcg", "ndcg_eval_at": [1, 3], "num_leaves": 15,
          "learning_rate": 0.05, "min_data_in_leaf": 20, "feature_fraction": 0.9, "verbose": -1, "seed": 7,
          "deterministic": True}
ROUNDS = 400
#: Bump when the fetch or the features change, so cached candidates are not reused.
CACHE_VERSION = "v3"


def normalise(text: str) -> str:
    text = "".join(c for c in text.lower() if c not in set(string.punctuation))
    return " ".join(w for w in text.split() if w not in {"a", "an", "the"})


def contains(passage: str, answers: list[str]) -> bool:
    body = f" {normalise(passage)} "
    return any(a and f" {a} " in body for a in (normalise(x) for x in answers))


def questions(cache: Path, split: str) -> list[dict]:
    import pandas as pd

    path = cache / f"nq-open-{split}.parquet"
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(NQ.format(split=split), headers={"user-agent": webread.USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    frame = pd.read_parquet(path)
    return [{"q": q, "answers": list(a)} for q, a in zip(frame["question"], frame["answer"], strict=True)]


def held_out_questions() -> set[str]:
    import yaml

    found = set()
    for name in ("dev", "test", "test2"):
        path = ROOT / "benchmark" / "ask" / f"{name}.yaml"
        if path.exists():
            found |= {normalise(q["q"]) for q in yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]}
    return found


def fetch(question: str) -> list[webread.Document]:
    for attempt in range(4):
        try:
            return webread.wikipedia(question)
        except Exception:
            time.sleep(2 ** attempt)
    return []


def collect(items: list[dict], path: Path, workers: int = 3) -> list[dict]:
    """Every question's candidates with features and labels, cached as JSON lines so a rerun only
    fetches what is missing."""
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["q"]] = row
    todo = [it for it in items if it["q"] not in done]

    def one(item: dict) -> dict:
        docs = fetch(item["q"])
        rows = [{"f": f, "y": int(contains(text, item["answers"])), "title": doc.title}
                for doc, text, f in webread.candidates(item["q"], docs)]
        return {"q": item["q"], "answers": item["answers"], "candidates": rows}

    with path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        for i, row in enumerate(pool.map(one, todo), 1):
            out.write(json.dumps(row) + "\n")
            done[row["q"]] = row
            if i % 100 == 0:
                print(f"  fetched {i}/{len(todo)}", flush=True)
    return [done[it["q"]] for it in items]


def matrix(rows: list[dict]):
    import numpy as np

    X, y, groups = [], [], []
    for row in rows:
        cands = row["candidates"]
        if not cands or not any(c["y"] for c in cands) or all(c["y"] for c in cands):
            continue  # a question with nothing to order teaches nothing
        X += [[c["f"][k] for k in webread.FEATURES] for c in cands]
        y += [c["y"] for c in cands]
        groups.append(len(cands))
    return np.array(X, dtype=float), np.array(y), groups


def answer_at_1(rows: list[dict], score) -> list[int]:
    hits = []
    for row in rows:
        cands = row["candidates"]
        if not cands:
            hits.append(0)
            continue
        best = max(range(len(cands)), key=lambda i: (score(cands[i]["f"]), -i))
        hits.append(cands[best]["y"])
    return hits


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def sign_test(a: list[int], b: list[int]) -> dict:
    """Exact two-sided sign test on the questions where the two rankers disagree."""
    wins = sum(1 for x, y in zip(a, b, strict=True) if x > y)
    losses = sum(1 for x, y in zip(a, b, strict=True) if x < y)
    n = wins + losses
    tail = sum(math.comb(n, k) for k in range(0, min(wins, losses) + 1)) / 2**n if n else 1.0
    return {"wins": wins, "losses": losses, "p": round(min(1.0, 2 * tail), 6)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--train", type=int, default=3000)
    parser.add_argument("--test", type=int, default=800)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    import lightgbm as lgb

    banned = held_out_questions()
    rng = random.Random(args.seed)
    train_pool = [q for q in questions(args.cache, "train") if normalise(q["q"]) not in banned]
    test_pool = [q for q in questions(args.cache, "validation") if normalise(q["q"]) not in banned]
    train_items = rng.sample(train_pool, min(args.train, len(train_pool)))
    test_items = rng.sample(test_pool, min(args.test, len(test_pool)))
    print(f"collecting {len(train_items)} train and {len(test_items)} test questions", flush=True)
    train_rows = collect(train_items, args.cache / f"train-{args.seed}-{CACHE_VERSION}.jsonl")
    test_rows = collect(test_items, args.cache / f"test-{args.seed}-{CACHE_VERSION}.jsonl")

    cut = int(len(train_rows) * 0.9)
    X, y, g = matrix(train_rows[:cut])
    Xv, yv, gv = matrix(train_rows[cut:])
    booster = lgb.train(PARAMS, lgb.Dataset(X, y, group=g, feature_name=list(webread.FEATURES)), ROUNDS,
                        valid_sets=[lgb.Dataset(Xv, yv, group=gv)],
                        callbacks=[lgb.early_stopping(40, verbose=False)])
    model = {**trees.compact(booster.dump_model(num_iteration=booster.best_iteration), list(webread.FEATURES)),
             "version": "brahmacharini-ranker-v0"}

    learned = webread.scorer(model)
    arms = {
        "ranker": answer_at_1(test_rows, learned),
        "heuristic": answer_at_1(test_rows, webread.heuristic),
        "source order": answer_at_1(test_rows, lambda f: -(f["doc_rank"] * 1000 + f["position"])),
    }
    ceiling = [int(any(c["y"] for c in r["candidates"])) for r in test_rows]
    n = len(test_rows)
    results = {
        "model": "brahmacharini-ranker-v0",
        "data": "Natural Questions (open), CC BY-SA 3.0; passages from Wikipedia introductions, CC BY-SA 4.0",
        "train_questions": len(train_rows), "test_questions": n,
        "trained_on_questions": len(g), "best_iteration": booster.best_iteration,
        "answer_at_1": {k: {"rate": round(sum(v) / n, 4), "ci95": wilson(sum(v), n)} for k, v in arms.items()},
        "ceiling": {"rate": round(sum(ceiling) / n, 4), "ci95": wilson(sum(ceiling), n),
                    "meaning": "a candidate passage contains the answer at all"},
        "ranker_vs_heuristic": sign_test(arms["ranker"], arms["heuristic"]),
        "importance": dict(sorted(zip(webread.FEATURES, (float(v) for v in booster.feature_importance("gain")),
                                      strict=True), key=lambda kv: -kv[1])),
        "params": PARAMS, "seed": args.seed,
    }
    served = results["answer_at_1"]["ranker"]["rate"] > results["answer_at_1"]["heuristic"]["rate"]
    results["served"] = served
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (args.out / "model.json").write_text(json.dumps(model), encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("answer_at_1", "ceiling", "ranker_vs_heuristic", "served")}, indent=2))
    if args.export and served:
        args.export.mkdir(parents=True, exist_ok=True)
        (args.export / "brahmacharini_ranker.json").write_text(json.dumps(model), encoding="utf-8")
        print(f"exported to {args.export / 'brahmacharini_ranker.json'}")
    elif args.export:
        print("not exported: the ranker did not beat the hand-set score", file=sys.stderr)


if __name__ == "__main__":
    main()
