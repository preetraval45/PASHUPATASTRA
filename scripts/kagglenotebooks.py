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
             "detection of new attacks. This plain model (no class weighting, default threshold) falls to about "
             "0.12 on unseen days; Chandraghanta, with class weighting and a threshold chosen on a validation "
             "slice, reaches 0.453, still far below the 0.997 a random split suggests. Per family, web attacks "
             "transfer; port scans and bots do not. Its numbers are in the attached results file."),
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
            ("markdown", "**Reading it:** on HDFS, event counts separate failing sessions almost perfectly; a plain "
             "model on this copy's row order scores about 0.999, and beats the classic PCA detector (Xu et al., "
             "2009). This copy's rows are not strictly in time order, so the split is easier than a true time "
             "split: Kalaratri, split by each session's first timestamp, reaches 0.966. On BGL, where failures are "
             "rarer and less templated, it reaches only 0.355. HDFS alone flatters log anomaly detection."),
        ],
    },

    "brahmacharini": {
        "title": "Brahmacharini: Which ATT&CK Technique Is This?",
        "datasets": [f"{OWNER}/sati-brahmacharini-attack-behaviour-to-technique"],
        "cells": [
            ("markdown", intro("Brahmacharini", "which ATT&CK technique is this behaviour?",
             "Real attacker behaviours from MITRE ATT&CK, each labelled with its technique. The test split holds "
             "groups, malware and tools never seen in training. Below: a TF-IDF retriever, a trained classifier, "
             "and what a random split would have claimed.")),
            ("code", FIND + """
import pandas as pd, numpy as np
b = pd.read_csv(find("behaviours.csv")); t = pd.read_csv(find("techniques.csv"))
print(b["split"].value_counts().to_dict(), len(t), "techniques")"""),
            ("code", """from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
train, test = b[b["split"] == "train"], b[b["split"] == "test"]
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit(pd.concat([train["behaviour"], t["text"]]))
sims = (vec.transform(test["behaviour"]) @ vec.transform(t["text"]).T).toarray()
ranked = t["technique_id"].values[np.argsort(-sims, axis=1)]
print(f"TF-IDF retrieval  recall@1 {np.mean(ranked[:, 0] == test['technique_id'].values):.3f}  "
      f"recall@10 {np.mean([g in r[:10] for g, r in zip(test['technique_id'], ranked)]):.3f}")
clf = LogisticRegression(max_iter=2000, C=5).fit(vec.transform(train["behaviour"]), train["technique_id"])
print(f"trained classifier recall@1 {clf.score(vec.transform(test['behaviour']), test['technique_id']):.3f}")"""),
            ("code", """from sklearn.model_selection import train_test_split
ra, rb = train_test_split(b, test_size=0.2, random_state=7)
leaky = LogisticRegression(max_iter=2000, C=5).fit(vec.transform(ra["behaviour"]), ra["technique_id"])
print(f"same classifier on a random split: {leaky.score(vec.transform(rb['behaviour']), rb['technique_id']):.3f}")"""),
            ("markdown", "**Reading it:** two honest surprises. First, the random split scores the same as the "
             "by-source split here, so for this classifier, a group's phrasing does not leak much. Second, this "
             "simple TF-IDF + logistic regression classifier (about 0.65 recall@1) **beats Brahmacharini** (0.614), "
             "the project's dual encoder, on the same split. Brahmacharini's advantage is elsewhere: one vector "
             "space for behaviours, techniques and knowledge-base passages, so it also retrieves the passage Sati "
             "cites. The project now reports this baseline beside it."),
        ],
    },
    "skandamata": {
        "title": "Skandamata: Which Mitigations Stop This Attack?",
        "datasets": [f"{OWNER}/sati-skandamata-attack-behaviour-to-mitigations"],
        "cells": [
            ("markdown", intro("Skandamata", "which defences stop what the attacker did?",
             "Each behaviour is labelled with every ATT&CK mitigation linked to its technique (2.8 on average). "
             "Rank the 44 mitigations; the split is by source, so test behaviours describe unseen attackers.")),
            ("code", FIND + """
import pandas as pd, numpy as np
b = pd.read_csv(find("behaviours.csv")); mit = pd.read_csv(find("mitigations.csv"))
ids = list(mit["mitigation_id"])
Y = np.array([[m in set(str(x).split(";")) for m in ids] for x in b["mitigation_ids"]], dtype=int)
train, test = (b["split"] == "train").values, (b["split"] == "test").values
print(Y.sum(1).mean().round(2), "right mitigations per behaviour")"""),
            ("code", """from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit(b.loc[train, "behaviour"])
keep = Y[train].sum(0) > 0
model = OneVsRestClassifier(LogisticRegression(max_iter=1000, C=4)).fit(vec.transform(b.loc[train, "behaviour"]), Y[train][:, keep])
scores = np.full((test.sum(), len(ids)), -1.0)
scores[:, keep] = model.predict_proba(vec.transform(b.loc[test, "behaviour"]))
top = scores.argmax(1)
print(f"trained    hit@1 {Y[test][np.arange(test.sum()), top].mean():.3f}")
popular = Y[train].sum(0).argmax()
print(f"popularity hit@1 {Y[test][:, popular].mean():.3f}  (always recommend the most common mitigation)")"""),
            ("markdown", "**Reading it:** a few mitigations (audit, user training) apply to most techniques, so "
             "popularity is a real baseline (0.232). This TF-IDF + logistic regression model (about 0.83 hit@1) "
             "**beats Skandamata** (0.790), the project's own model, on the same split; the project now reports it "
             "beside Skandamata. In Sati, recommendations follow the technique Brahmacharini identifies, and a "
             "person or the policy engine decides."),
        ],
    },
    "kushmanda": {
        "title": "Kushmanda: Answer From Evidence, Cite, or Decline",
        "datasets": [f"{OWNER}/sati-kushmanda-data"],
        "cells": [
            ("markdown", intro("Kushmanda", "answer from the evidence, cite it, or decline",
             "Each question comes with three passages. A good answer is written from one passage and ends with its "
             "citation, e.g. `[2]`; when no passage answers, the right reply is `The context does not answer "
             "this.` Below: the data, and the baselines any model must beat.")),
            ("code", FIND + """
import json, re, pandas as pd
def load(name):
    return pd.DataFrame([json.loads(line) for line in open(find(name), encoding="utf-8")])
train, test = load("train.jsonl"), load("test.jsonl")
print(len(train), "train /", len(test), "test")
print(test["kind"].value_counts().to_dict())
r = test.iloc[0]
print("Q:", r["question"])
for i, p in enumerate(r["passages"], 1):
    print(f"[{i}]", p[:160])
print("A:", r["answer"])"""),
            ("code", """def words(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))
def pick(q, passages):
    scores = [len(words(q) & words(p)) for p in passages]
    return max(range(len(passages)), key=lambda i: scores[i]) + 1
def cited(a):
    m = re.search(r"\\[(\\d)\\]\\s*$", a)
    return int(m.group(1)) if m else None
gold = [cited(a) for a in test["answer"]]
picked = [pick(q, ps) for q, ps in zip(test["question"], test["passages"])]
answerable = [g is not None for g in gold]
print(f"word overlap picks the right passage: {sum(p == g for p, g in zip(picked, gold) if g) / sum(answerable):.3f}")
print(f"share of questions that must be declined: {1 - sum(answerable) / len(test):.3f}")"""),
            ("markdown", "**Reading it:** picking the right passage is easy for word overlap; writing the answer, "
             "and knowing when to decline, is the task. Kushmanda (17M parameters, trained from scratch on this "
             "data's train split) reaches ROUGE-L 0.938 on required actions and declines on 0.543 of unanswerable "
             "questions, but copies exact identifiers worse than word overlap, so Sati takes identifiers from "
             "retrieval and lets the model write around them."),
        ],
    },
    "shailaputri": {
        "title": "Shailaputri: Server Anomalies on Unseen Machines",
        "datasets": [f"{OWNER}/sati-shailaputri-smd-server-anomalies"],
        "cells": [
            ("markdown", intro("Shailaputri", "is this server behaving abnormally right now?",
             "28 real servers (SMD), one row per minute with causal features. Hold out one machine group at a time: "
             "the model is always tested on servers it never saw. The false-alarm rate is reported beside F1, "
             "because an alert stream nobody reads is the real failure.")),
            ("code", FIND + """
import pandas as pd, numpy as np
d = pd.read_parquet(find("minutes.parquet"))
feats = [c for c in d.columns if c not in ("machine", "group", "minute", "anomaly")]
print(d.shape, d.groupby("group")["machine"].nunique().to_dict(), "anomaly share", round(d["anomaly"].mean(), 4))"""),
            ("code", """import lightgbm as lgb
from sklearn.metrics import f1_score
rows = []
for held in sorted(d["group"].unique()):
    tr, te = d[d["group"] != held], d[d["group"] == held]
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, verbose=-1).fit(tr[feats], tr["anomaly"])
    p_tr = m.predict_proba(tr[feats])[:, 1]
    t = max(np.arange(0.3, 0.96, 0.05), key=lambda t: f1_score(tr["anomaly"], p_tr >= t))  # chosen on training groups
    flag = m.predict_proba(te[feats])[:, 1] >= t
    rows.append({"held out": held, "F1 (per minute)": f1_score(te["anomaly"], flag),
                 "false alarms / 1000 normal minutes": 1000 * flag[te["anomaly"].values == 0].mean()})
pd.DataFrame(rows).round(3)"""),
            ("markdown", "**Reading it:** these are per-minute scores. The project scores per anomaly *episode* "
             "with lead time, where Shailaputri reaches F1 0.556 with 4.6 false alarms per 1000 minutes, against "
             "0.419 and 86.6 for per-machine PCA."),
        ],
    },
    "mahagauri": {
        "title": "Mahagauri: Is the Incident Really Over?",
        "datasets": [f"{OWNER}/sati-mahagauri-server-recovery"],
        "cells": [
            ("markdown", intro("Mahagauri", "has the server really recovered?",
             "327 real server incidents, minute by minute from onset to an hour after. Declare the incident over "
             "once the model says 'recovered' for several minutes running. The dangerous error is declaring it "
             "over while it is still going.")),
            ("code", FIND + """
import pandas as pd, numpy as np
d = pd.read_parquet(find("recovery.parquet"))
feats = [c for c in d.columns if c not in ("incident", "group", "recovered")]
print(d["incident"].nunique(), "incidents")"""),
            ("code", """import lightgbm as lgb
def outcome(recovered, ok, hold):
    end = int(recovered.argmax()) if recovered.any() else len(recovered)
    run = 0
    for i, v in enumerate(ok):
        run = run + 1 if v else 0
        if run >= hold:
            return "premature" if i < end else "confirmed"
    return "unconfirmed"
rows = []
for held in sorted(d["group"].unique()):
    tr, te = d[d["group"] != held], d[d["group"] == held].copy()
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, verbose=-1).fit(tr[feats], tr["recovered"])
    te["p"] = m.predict_proba(te[feats])[:, 1]
    for t, hold in ((0.5, 3), (0.9, 10)):
        res = pd.Series([outcome(g["recovered"].values, g["p"].values >= t, hold) for _, g in te.groupby("incident")])
        rows.append({"held out": held, "threshold": t, "hold (min)": hold, **res.value_counts(normalize=True).round(3).to_dict()})
pd.DataFrame(rows).fillna(0)"""),
            ("markdown", "**Reading it:** a lenient rule confirms more recoveries but declares many too early; a "
             "strict one is safe and rarely says anything. Mahagauri, tuned on out-of-fold scores, keeps premature "
             "all-clears at 0.021 on unseen groups but confirms only 0.095: making a verifier both safe and useful "
             "is open."),
        ],
    },
    "siddhidatri": {
        "title": "Siddhidatri: Fusing Detectors, and Calibration",
        "datasets": [f"{OWNER}/sati-siddhidatri-detector-scores"],
        "cells": [
            ("markdown", intro("Siddhidatri", "one calibrated verdict from three detectors",
             "Per-minute scores from a learned detector (trained without the minute's machine group) and two "
             "statistical ones. Fuse them with logistic regression, held out by group, and check whether fusion "
             "beats the best single detector and whether its probabilities mean what they say.")),
            ("code", FIND + """
import pandas as pd, numpy as np
d = pd.read_parquet(find("detector_scores.parquet")).fillna(0)
S = ["shailaputri", "max_robust_z", "pca"]
print(d.shape)"""),
            ("code", """from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
rows = []
for held in sorted(d["group"].unique()):
    tr, te = d[d["group"] != held], d[d["group"] == held]
    fused = LogisticRegression(max_iter=1000).fit(tr[S], tr["anomaly"]).predict_proba(te[S])[:, 1]
    row = {"held out": held, "fused AUC": roc_auc_score(te["anomaly"], fused),
           "fused Brier": brier_score_loss(te["anomaly"], fused)}
    for s in S:
        row[f"{s} AUC"] = roc_auc_score(te["anomaly"], te[s])
    rows.append(row)
pd.DataFrame(rows).round(3)"""),
            ("markdown", "**Reading it:** if fused AUC barely beats the learned detector alone, fusion buys little. "
             "Siddhidatri matched Shailaputri's F1 (0.537 against 0.539) with far more false alarms (47.8 against "
             "3.8 per 1000). A fusion that catches more at the same false-alarm rate would be a new result."),
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
