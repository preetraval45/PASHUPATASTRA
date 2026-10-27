"""Write the nine public Kaggle notebooks, one per Sati model.

    python scripts/kagglenotebooks.py --out kaggle/notebooks

Each notebook loads that model's public dataset, trains a model on it and
reports held-out results with the split that makes them honest (by group, by
source, by day or by time, never a random split where that would leak). They
run on Kaggle's free CPU in minutes, so anyone can check a number.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OWNER = "preetraval4518071604"
REPO = "https://github.com/preetraval45/PASHUPATASTRA"

FIND = '''import glob, os
def find(pattern):
    hits = glob.glob(f"/kaggle/input/**/{pattern}", recursive=True)
    assert hits, f"{pattern} not found under /kaggle/input"
    return hits[0]'''


def slug(title: str) -> str:
    """Kaggle derives a notebook's address from its title; matching it avoids a duplicate."""
    import re
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")


def notebook(cells: list[tuple[str, str]]) -> dict:
    def cell(kind: str, text: str) -> dict:
        base = {"cell_type": kind, "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}
        return {**base, "execution_count": None, "outputs": []} if kind == "code" else base
    return {"cells": [cell(k, t) for k, t in cells], "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3",
            "language": "python"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def intro(form: str, job: str, body: str) -> str:
    return (f"# {form}: {job}\n\n{body}\n\n{form} is one of the nine models of **Sati**, the investigation agent of "
            f"[Pashupatastra]({REPO}), each named for a form of Navadurga. This notebook reproduces its core result "
            "on the public dataset, with the split that keeps the test honest.")


NOTEBOOKS: dict[str, dict] = {
    "katyayani": {
        "title": "Katyayani: Root Cause on Live Fault Injections",
        "datasets": [f"{OWNER}/sati-katyayani-live-fault-injections"],
        "cells": [
            ("markdown", intro("Katyayani", "which service caused the incident?",
             "200 real fault injections on an 8-service Kubernetes cluster. For each incident, rank the services so "
             "the injected root comes first. Two rankers: the **loudest service** (largest metric shift, no learning) "
             "and a **learned ranker** tested leave-one-fault-out, so it never trains on the fault type it is "
             "scored on.")),
            ("code", FIND + '''
import numpy as np, pandas as pd
incidents = pd.read_csv(find("incidents.csv"))
metrics = pd.read_parquet(find("metrics.parquet"))
incidents = incidents[incidents["error"].isna() | (incidents["error"] == "")]
print(len(incidents), "incidents;", metrics.shape, "metric rows")
incidents["fault"].value_counts()'''),
            ("markdown", "## Features: how far each metric moved, against its own baseline\n\nFor each service and "
             "metric: the robust shift of the median after injection against the 2 minutes before, in units of the "
             "baseline's spread. Log-compressed, because steady baselines make raw z-scores enormous."),
            ("code", '''METRICS = ["cpu_cores", "memory_bytes", "latency_p90_ms", "requests_per_s", "error_rate"]
rows = []
for inc in incidents.itertuples():
    m = metrics[metrics["incident"] == inc.incident]
    before, after = m[m["time"] < inc.inject_time], m[m["time"] >= inc.inject_time]
    for svc in m["service"].unique():
        b, a = before[before["service"] == svc], after[after["service"] == svc]
        row = {"incident": inc.incident, "fault": inc.fault, "service": svc, "root": int(svc == inc.root_service)}
        for c in METRICS:
            base = b[c].dropna(); post = a[c].dropna()
            if len(base) < 2 or not len(post):
                row[c] = 0.0; continue
            scale = (base.quantile(.75) - base.quantile(.25)) / 1.349 or base.std() or 1e-6
            z = (post.median() - base.median()) / (scale if scale > 0 else 1e-6)
            row[c] = float(np.sign(z) * np.log1p(abs(z)))
        rows.append(row)
table = pd.DataFrame(rows)
table["peak"] = table[METRICS].abs().max(axis=1)
table.head()'''),
            ("code", '''def rca_at_1(scored, score):
    top = scored.loc[scored.groupby("incident")[score].idxmax()]
    return top["root"].mean()

print(f"loudest service RCA@1: {rca_at_1(table, 'peak'):.3f}   (chance: {1 / table.groupby('incident').size().mean():.3f})")'''),
            ("markdown", "## A learned ranker, leave one fault type out"),
            ("code", '''import lightgbm as lgb
FEATS = METRICS + ["peak"]
table["rank_in_incident"] = table.groupby("incident")["peak"].rank(ascending=False)
FEATS.append("rank_in_incident")
results = {}
for fault in sorted(table["fault"].unique()):
    train, test = table[table["fault"] != fault].sort_values("incident"), table[table["fault"] == fault].copy()
    model = lgb.LGBMRanker(n_estimators=200, learning_rate=0.05, num_leaves=15, verbose=-1)
    model.fit(train[FEATS], train["root"], group=train.groupby("incident").size().values)  # sorted by incident
    test["score"] = model.predict(test[FEATS])
    results[fault] = {"learned": rca_at_1(test, "score"), "loudest": rca_at_1(test, "peak")}
pd.DataFrame(results).T.round(3)'''),
            ("markdown", "**Reading it:** the loudest service is a strong rule on this stack, because a fault here "
             "mostly makes its own service move most. The bad-release fault is the hard case: a failing release "
             "raises errors at every caller up the chain. Katyayani, trained on *other* systems (RCAEval), ranks "
             "the root first in 0.895 of these incidents; see the project's paper for that sim-to-real result."),
        ],
    },
    "chandraghanta": {
        "title": "Chandraghanta: Intrusion Detection on Unseen Days",
        "datasets": [f"{OWNER}/sati-chandraghanta-ids-split-benchmark", "dhoogla/cicids2017"],
        "cells": [
            ("markdown", intro("Chandraghanta", "is this network flow an attack?",
             "CIC-IDS2017, attached from its public Kaggle copy (it is not redistributed here). The usual protocol "
             "splits flows at random and reports near-perfect scores. Here the split is **by day**: train on "
             "Monday–Wednesday, test on Thursday–Friday, so every test attack family is one the model never saw.")),
            ("code", FIND + '''
import pandas as pd, numpy as np
frames = []
for path in sorted(glob.glob("/kaggle/input/**/*-no-metadata.parquet", recursive=True)):
    df = pd.read_parquet(path)
    df["day"] = os.path.basename(path).split("-")[1]
    frames.append(df)
data = pd.concat(frames, ignore_index=True)
label = next(c for c in data.columns if c.strip().lower() == "label")
data["attack"] = (data[label].astype(str).str.upper() != "BENIGN").astype(int)
print(data.shape); data.groupby("day")["attack"].mean().round(3)'''),
            ("code", '''import lightgbm as lgb
from sklearn.metrics import f1_score
features = [c for c in data.columns if c not in (label, "day", "attack") and pd.api.types.is_numeric_dtype(data[c])]
X = data[features].replace([np.inf, -np.inf], np.nan)
train = data["day"].isin(["Monday", "Tuesday", "Wednesday"])
model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=63, verbose=-1)
model.fit(X[train], data.loc[train, "attack"])
pred = model.predict(X[~train])
print(f"F1 on unseen days: {f1_score(data.loc[~train, 'attack'], pred):.3f}")

from sklearn.model_selection import train_test_split
xa, xb, ya, yb = train_test_split(X, data["attack"], test_size=0.2, random_state=7)
print(f"F1 on a random split: {f1_score(yb, lgb.LGBMClassifier(n_estimators=300, verbose=-1).fit(xa, ya).predict(xb)):.3f}")'''),
            ("code", '''test = data[~train].assign(pred=pred)
test[test["attack"] == 1].groupby(label)["pred"].agg(["mean", "size"]).rename(columns={"mean": "recall", "size": "flows"}).round(3)'''),
            ("markdown", "**Reading it:** the gap between the two F1 scores is the point. A random split puts flows "
             "from the same attack session on both sides, so it measures recognition of known traffic, not "
             "detection of new attacks. Per family, brute-force-like web attacks transfer; port scans and bots do "
             "not. The attached results file holds Chandraghanta's own numbers (F1 0.997 random, 0.453 unseen days)."),
        ],
    },
    "kalaratri": {
        "title": "Kalaratri: Log Anomalies, Split by Time",
        "datasets": [f"{OWNER}/sati-kalaratri-log-anomaly-time-split", "tamaniwilliams/hdfs-v1-loghub-dataset-archive"],
        "cells": [
            ("markdown", intro("Kalaratri", "which log sessions are failing?",
             "LogHub HDFS, attached from its public Kaggle copy (research use; not redistributed here). Each block "
             "is a session of log events; its label says whether it failed. Train on the earlier 80% of sessions and "
             "test on the later 20%, so the model is tested on the future, never on a shuffled past.")),
            ("code", FIND + '''
import pandas as pd, numpy as np
m = pd.read_csv(find("Event_occurrence_matrix.csv"))
label = next(c for c in m.columns if c.lower() == "label")
m["anomaly"] = m[label].astype(str).str.lower().str.contains("fail|anomal").astype(int)
events = [c for c in m.columns if c.startswith("E") and c[1:].isdigit()]
print(m.shape, "anomaly share", round(m["anomaly"].mean(), 4))'''),
            ("code", '''import lightgbm as lgb
from sklearn.metrics import f1_score, precision_score, recall_score
cut = int(len(m) * 0.8)
X, y = np.log1p(m[events]), m["anomaly"]
model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1).fit(X[:cut], y[:cut])
pred = model.predict(X[cut:])
print(f"precision {precision_score(y[cut:], pred):.3f}  recall {recall_score(y[cut:], pred):.3f}  F1 {f1_score(y[cut:], pred):.3f}")'''),
            ("code", '''from sklearn.decomposition import PCA
normal = X[:cut][y[:cut] == 0]
pca = PCA(n_components=0.95).fit(normal)
err = ((X[cut:] - pca.inverse_transform(pca.transform(X[cut:]))) ** 2).sum(axis=1)
threshold = np.quantile(((normal - pca.inverse_transform(pca.transform(normal))) ** 2).sum(axis=1), 0.995)
print(f"PCA baseline F1: {f1_score(y[cut:], err > threshold):.3f}")'''),
            ("markdown", "**Reading it:** on HDFS, event counts separate failing sessions almost perfectly, and a "
             "learned model beats the classic PCA detector (Xu et al., 2009). Kalaratri reaches F1 0.966 here, but "
             "only 0.355 on BGL, where failures are rarer and less templated: HDFS alone flatters log anomaly "
             "detection. Both results are in the attached files."),
        ],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("kaggle/notebooks"))
    args = parser.parse_args()
    for form, spec in NOTEBOOKS.items():
        folder = args.out / form
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "notebook.ipynb").write_text(json.dumps(notebook(spec["cells"]), indent=1), encoding="utf-8")
        (folder / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{OWNER}/{slug(spec['title'])}", "title": spec["title"], "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": False, "enable_gpu": False,
            "enable_internet": False, "dataset_sources": spec["datasets"], "competition_sources": [],
            "kernel_sources": [], "model_sources": spec.get("models", [])}, indent=1), encoding="utf-8")
        print("wrote", folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
