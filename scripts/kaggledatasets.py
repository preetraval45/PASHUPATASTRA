"""Build the nine public Kaggle datasets, one per Sati model, from data we may republish.

    python scripts/kaggledatasets.py --out build/kaggle --cache .cache   # runs on Kaggle (internet, CPU)

Each folder holds tidy files and a `dataset-metadata.json` with the title,
subtitle, description, licence, tags and a description of every file and
column. Licences follow docs/research/datasheets.md: this project's own data is
CC-BY-4.0; ATT&CK, CAPEC, CWE, KEV and NVD-derived data carry their sources'
terms and attribution; SMD-derived data is MIT. UNSW-NB15, CIC-IDS2017 and
LogHub are research-use only and are never redistributed: their datasets hold
only this project's split definitions and results, and their notebooks attach
the original data from its own Kaggle copies.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "sati"))
sys.path.insert(0, str(ROOT / "packages" / "core"))

OWNER = "preetraval4518071604"
REPO = "https://github.com/preetraval45/PASHUPATASTRA"
MITRE = ("MITRE ATT&CK® content is © The MITRE Corporation, reproduced under MITRE's terms of use "
         "(royalty-free, with attribution). ATT&CK® is a registered trademark of The MITRE Corporation.")
FOOT = (f"\n\n## Provenance\n\nBuilt by `scripts/kaggledatasets.py` in [{REPO}]({REPO}), the Pashupatastra project, "
        "from pinned public sources. Sati is the project's investigation agent; each of its nine models is named "
        "for a form of Navadurga, and this dataset belongs to one of them. Every number in the project's research "
        "paper about it is regenerated from committed results.")


def field(name: str, description: str, kind: str = "string") -> dict:
    return {"name": name, "description": description, "type": kind}


def write(folder: Path, slug: str, title: str, subtitle: str, description: str, licence: str,
          keywords: list[str], resources: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"title": title, "subtitle": subtitle, "id": f"{OWNER}/{slug}", "licenses": [{"name": licence}],
            "keywords": keywords, "description": description + FOOT, "resources": resources}
    (folder / "dataset-metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"built {slug}: {[r['path'] for r in resources]}")


# --- Katyayani: the live fault-injection incidents ---------------------------

def katyayani(out: Path) -> None:
    from benchmark.live.topology import CALLS, LAYER

    folder = out / "katyayani"
    folder.mkdir(parents=True, exist_ok=True)
    data = ROOT / "benchmark" / "live" / "dataset"
    with gzip.open(data / "incidents.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    incidents, metrics, deploys = [], [], []
    for r in records:
        incidents.append({"incident": r["id"], "fault": r["fault"], "root_service": r["root"],
                          "inject_time": r.get("inject_time"), "injected": r.get("injected", ""),
                          "error": r.get("error", "")})
        for s in r.get("samples", []):
            if s.get("up"):
                metrics.append({"incident": r["id"], "time": s["t"], "service": s["service"], "cpu_cores": s["cpu"],
                                "memory_bytes": s["mem"], "latency_p90_ms": s["latency-90"],
                                "requests_per_s": s["request"], "error_rate": s["error"]})
        for svc, times in r.get("deploys", {}).items():
            deploys += [{"incident": r["id"], "service": svc, "time": t} for t in times]
    pd.DataFrame(incidents).to_csv(folder / "incidents.csv", index=False)
    pd.DataFrame(metrics).to_parquet(folder / "metrics.parquet", index=False)
    pd.DataFrame(deploys).to_csv(folder / "deploys.csv", index=False)
    pd.DataFrame([{"caller": a, "callee": b} for a, b in CALLS]).to_csv(folder / "topology.csv", index=False)
    services = sorted({x for e in CALLS for x in e})
    pd.DataFrame([{"service": s, "layer": LAYER.get(s, "backend")} for s in services]).to_csv(
        folder / "services.csv", index=False)
    write(folder, "sati-katyayani-live-fault-injections",
          "Live Microservice Fault Injections (200 incidents)",
          "Real CPU, memory, delay and bad-release faults on an 8-service cluster, labelled",
          "200 fault injections run on a real Kubernetes (kind) cluster: an eight-service application under steady "
          "load, one fault injected per incident at a root service chosen by a seeded plan committed before any run. "
          "Faults are CPU saturation, memory growth, 400 ms added latency, and a bad release that fails 30% of "
          "requests. Every service reports its own metrics every 5 seconds, from its container's cgroup and its "
          "request handler.\n\n**Task:** root-cause analysis: rank the services; the injected root is the answer. "
          "This is the sim-to-real test set Katyayani (Sati's root-cause model) is evaluated on: trained on other "
          "systems, it ranks the root first in 0.895 of these incidents, against 0.870 for the loudest service and "
          "0.125 by chance.\n\n**Note:** baselines are steady, so robust z-scores are large for every service; "
          "compare services against each other, not against a fixed σ threshold.",
          "CC-BY-4.0", ["computer science", "software", "time series analysis", "kubernetes", "anomaly detection"],
          [{"path": "incidents.csv", "description": "One row per planned incident: the fault and the true root.",
            "schema": {"fields": [field("incident", "Incident id"), field("fault", "cpu, mem, delay or release"),
                                  field("root_service", "The service the fault was injected into (the answer)"),
                                  field("inject_time", "Unix seconds at injection", "integer"),
                                  field("injected", "What was done, in words"),
                                  field("error", "Non-empty if the run failed; such incidents have no metrics")]}},
           {"path": "metrics.parquet", "description": "Every service's metrics, every 5 s, 2 min before to 2.5 min after.",
            "schema": {"fields": [field("incident", "Incident id"), field("time", "Unix seconds", "integer"),
                                  field("service", "Service name"), field("cpu_cores", "CPU cores used", "number"),
                                  field("memory_bytes", "Container memory", "number"),
                                  field("latency_p90_ms", "90th percentile request latency", "number"),
                                  field("requests_per_s", "Request rate", "number"),
                                  field("error_rate", "Share of requests that failed", "number")]}},
           {"path": "deploys.csv", "description": "ReplicaSet creation times per service (deploy events).",
            "schema": {"fields": [field("incident", "Incident id"), field("service", "Service"),
                                  field("time", "Unix seconds", "integer")]}},
           {"path": "topology.csv", "description": "The call graph: each service's downstream calls.",
            "schema": {"fields": [field("caller", "Calling service"), field("callee", "Called service")]}},
           {"path": "services.csv", "description": "Each service's layer.",
            "schema": {"fields": [field("service", "Service"), field("layer", "edge, api, backend or store")]}}])


# --- Brahmacharini and Skandamata: ATT&CK behaviours ----------------------------

def brahmacharini(out: Path, cache: Path) -> None:
    from sati.embed import data as d

    folder = out / "brahmacharini"
    folder.mkdir(parents=True, exist_ok=True)
    techniques, procedures = d.load(cache)
    names = {t.stix_id: t for t in techniques}
    train, val, test = d.split_by_source(procedures)
    split = {id(p): s for s, part in (("train", train), ("validation", val), ("test", test)) for p in part}
    pd.DataFrame([{"behaviour": p.text, "technique_id": names[p.technique].attack_id, "source": p.source,
                   "split": split[id(p)]} for p in procedures if p.technique in names]).to_csv(
        folder / "behaviours.csv", index=False)
    pd.DataFrame([{"technique_id": t.attack_id, "text": t.text} for t in techniques]).to_csv(
        folder / "techniques.csv", index=False)
    write(folder, "sati-brahmacharini-attack-behaviour-to-technique",
          "ATT&CK Behaviour → Technique (split by source)",
          "17,000+ real attacker behaviours labelled with their ATT&CK technique, held out by group",
          "Every MITRE ATT&CK enterprise procedure example (how a named group, malware family, tool or campaign used a "
          "technique, written by analysts from public reporting), labelled with its technique. The split is **by "
          "source**: every procedure about one group, malware or tool lands on one side, so the test set describes "
          "attackers never seen in training. The usual random split leaks each group's phrasing into the test.\n\n"
          "**Task:** given a behaviour, rank all techniques. Brahmacharini (Sati's retrieval model) reaches "
          "Recall@1 0.614 and Recall@10 0.854 on the test split, against 0.268 and 0.580 for BM25.\n\n" + MITRE,
          "other", ["computer science", "nlp", "information retrieval", "cybersecurity"],
          [{"path": "behaviours.csv", "description": "One procedure example per row.",
            "schema": {"fields": [field("behaviour", "What the attacker did, in an analyst's words"),
                                  field("technique_id", "ATT&CK technique id (the label)"),
                                  field("source", "Group, malware, tool or campaign the text is about"),
                                  field("split", "train, validation or test (by source)")]}},
           {"path": "techniques.csv", "description": "Every live technique with its name and description.",
            "schema": {"fields": [field("technique_id", "ATT&CK id"), field("text", "Name and description")]}}])


def skandamata(out: Path, cache: Path) -> None:
    from sati.respond.data import build

    folder = out / "skandamata"
    folder.mkdir(parents=True, exist_ok=True)
    data = build(cache)
    ids = [m.attack_id for m in data.mitigations]
    rows = [{"behaviour": e.text, "source": e.source, "split": split, "mitigation_ids": ";".join(sorted(ids[i] for i in e.gold))}
            for split, part in (("train", data.train), ("validation", data.validation), ("test", data.test)) for e in part]
    pd.DataFrame(rows).to_csv(folder / "behaviours.csv", index=False)
    pd.DataFrame([{"mitigation_id": m.attack_id, "name": m.name, "description": m.text} for m in data.mitigations]).to_csv(
        folder / "mitigations.csv", index=False)
    write(folder, "sati-skandamata-attack-behaviour-to-mitigations",
          "ATT&CK Behaviour → Mitigations (multi-label)",
          "Which defences stop what an attacker did: 13,000 behaviours, 44 mitigations, split by source",
          "Each ATT&CK procedure example paired with every mitigation ATT&CK links to its technique (sub-techniques "
          "inherit their parent's). Split by source, so test behaviours describe attackers never seen in training.\n\n"
          "**Task:** rank the 44 mitigations for a behaviour. Skandamata (Sati's defence recommender) gets the first "
          "recommendation right 0.792 of the time, against 0.537 for BM25 over techniques and 0.232 for "
          "recommending the most common mitigations.\n\n" + MITRE,
          "other", ["computer science", "nlp", "multilabel classification", "cybersecurity"],
          [{"path": "behaviours.csv", "description": "One behaviour per row with its right mitigations.",
            "schema": {"fields": [field("behaviour", "What the attacker did"), field("source", "Who it is about"),
                                  field("split", "train, validation or test (by source)"),
                                  field("mitigation_ids", "Right mitigations, ';'-separated ATT&CK ids")]}},
           {"path": "mitigations.csv", "description": "The 44 ATT&CK enterprise mitigations.",
            "schema": {"fields": [field("mitigation_id", "ATT&CK id (M1xxx)"), field("name", "Name"),
                                  field("description", "What it does")]}}])


# --- Kushmanda: grounded question answering ----------------------------------

def kushmanda(out: Path, cache: Path) -> None:
    from sati.lm import sft

    folder = out / "kushmanda"
    folder.mkdir(parents=True, exist_ok=True)
    train, test = sft.build(cache)
    for name, part in (("train", train), ("test", test)):
        with (folder / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for p in part:
                f.write(json.dumps({"question": p["q"], "passages": p.get("context", []), "answer": p["a"],
                                    "kind": p.get("kind"), "entity": p.get("entity")}, ensure_ascii=False) + "\n")
    write(folder, "sati-kushmanda-data",
          "Grounded Security QA: answer from passages, cite, or decline",
          "Questions with 3 passages each; answers cite one, and some must be declined",
          "Question–answer pairs built from MITRE ATT&CK, CAPEC, CWE and CISA KEV. Each question comes with three "
          "passages; the answer is written from one of them and ends with its citation, e.g. `[2]`. About one "
          "question in ten has no passage that answers it, and the right answer is `The context does not answer "
          "this.` The split is by entity (technique, CVE, weakness), so test questions are about things unseen in "
          "training.\n\n**Task:** grounded generation with citation and abstention. Kushmanda (Sati's own 17M-"
          "parameter language model, trained from scratch) is tuned on the train split; on test it reaches ROUGE-L "
          "0.938 on required actions and declines on 0.543 of unanswerable questions.\n\n" + MITRE +
          " CISA KEV and NVD are U.S. government works.",
          "other", ["computer science", "nlp", "question answering", "cybersecurity"],
          [{"path": "train.jsonl", "description": "Training pairs (JSON lines).",
            "schema": {"fields": [field("question", "The question"), field("passages", "Three numbered passages"),
                                  field("answer", "Answer ending in its citation, or the refusal"),
                                  field("kind", "Question type"), field("entity", "The entity it is about")]}},
           {"path": "test.jsonl", "description": "Held-out pairs, about unseen entities (JSON lines).",
            "schema": {"fields": [field("question", "The question"), field("passages", "Three passages"),
                                  field("answer", "Reference answer"), field("kind", "Question type"),
                                  field("entity", "The entity")]}}])


# --- Shailaputri, Mahagauri, Siddhidatri: SMD --------------------------------

def smd_sets(out: Path, cache: Path) -> None:
    from sati.detect import smd as smd_run
    from sati.fuse import run as fuse
    from sati.sources import smd
    from sati.verify import run as verify

    machines = []
    for name in smd.MACHINES:
        m = smd.machine(name, cache / "smd", smd_run.REVISION)
        m["features"] = smd_run.aggregate(m["train"], m["test"])
        m["pca"] = smd_run.pca_relative(m)
        machines.append(m)
    groups = sorted({m["group"] for m in machines})
    licence_note = ("Derived from the Server Machine Dataset (SMD, NetManAIOps/OmniAnomaly, MIT licence), pinned "
                    f"to commit `{smd_run.REVISION[:12]}`. Cite Su et al., KDD 2019.")

    shail = out / "shailaputri"
    shail.mkdir(parents=True, exist_ok=True)
    frames = []
    for m in machines:
        f = m["features"].copy()
        f.insert(0, "minute", np.arange(len(f)))
        f.insert(0, "group", m["group"])
        f.insert(0, "machine", m["name"])
        f["anomaly"] = m["labels"]
        frames.append(f)
    table = pd.concat(frames, ignore_index=True)
    table.to_parquet(shail / "minutes.parquet", index=False)
    cols = [c for c in table.columns if c not in ("machine", "group", "minute", "anomaly")]
    write(shail, "sati-shailaputri-smd-server-anomalies",
          "Server Anomalies: Per-Minute Features for 28 Real Servers",
          "SMD's labelled test halves as causal per-minute features, with machine groups for honest splits",
          "The labelled halves of all 28 servers of the Server Machine Dataset, turned into per-minute features that "
          "use only the past (each metric's robust deviation over several windows, aggregated across the server's 38 "
          "metrics), with the anomaly label. Hold out a machine **group** to test on servers never seen.\n\n**Task:** "
          "flag anomalous minutes. Shailaputri (Sati's metric detector), holding out each group in turn, scores F1 "
          "0.556 with 4.6 false alarms per 1000 minutes, against 0.419 and 86.6 for per-machine PCA.\n\n" + licence_note,
          "other", ["computer science", "time series analysis", "anomaly detection"],
          [{"path": "minutes.parquet", "description": "One row per server-minute.",
            "schema": {"fields": [field("machine", "Server id"), field("group", "machine-1, -2 or -3"),
                                  field("minute", "Minute index in the test half", "integer"),
                                  *[field(c, "Causal feature aggregated across the server's metrics", "number") for c in cols],
                                  field("anomaly", "1 if labelled anomalous", "integer")]}}])

    maha = out / "mahagauri"
    maha.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in machines:
        for ep in verify.episodes(m):
            fr, y = verify.frame(ep), verify.labels(ep)
            fr.insert(0, "minute_since_onset", np.arange(len(fr)))
            fr.insert(0, "incident", f"{m['name']}@{ep['start']}")
            fr.insert(1, "group", m["group"])
            fr["recovered"] = y
            rows.append(fr)
    episodes = pd.concat(rows, ignore_index=True)
    episodes.to_parquet(maha / "recovery.parquet", index=False)
    write(maha, "sati-mahagauri-server-recovery",
          "Has the Server Recovered? Minute-by-Minute Incident Recovery",
          "327 real server incidents, from onset to an hour after: is it over yet?",
          "For every labelled anomaly in SMD with an hour of clean history before it, every minute from onset until "
          "an hour after it ends, with features comparing each metric to that incident's own pre-incident baseline, "
          "and whether the server has recovered.\n\n**Task:** declare an incident over without declaring it too "
          "early. The error that matters is a premature all-clear. Mahagauri (Sati's verifier), tuned on out-of-fold "
          "scores, keeps premature all-clears at 0.021 on unseen machine groups, but confirms only 0.092 of "
          "recoveries: separating 'recovered' from 'not yet' is the open problem.\n\n" + licence_note,
          "other", ["computer science", "time series analysis", "anomaly detection", "classification"],
          [{"path": "recovery.parquet", "description": "One row per incident-minute.",
            "schema": {"fields": [field("incident", "Server and onset minute"), field("group", "Machine group"),
                                  field("minute_since_onset", "Minutes since the anomaly began", "integer"),
                                  field("recovered", "1 once the labelled anomaly has ended", "integer")]}}])

    sidd = out / "siddhidatri"
    sidd.mkdir(parents=True, exist_ok=True)
    scored = []
    for held in groups:
        booster = fuse.fit([m for m in machines if m["group"] != held])
        for m in (m for m in machines if m["group"] == held):
            s = fuse.scores(m, booster, 0.999)
            scored.append(pd.DataFrame({"machine": m["name"], "group": held, "minute": np.arange(len(s)),
                                        "shailaputri": s[:, 0], "max_robust_z": s[:, 1], "pca": s[:, 2],
                                        "anomaly": m["labels"]}))
    pd.concat(scored, ignore_index=True).to_parquet(sidd / "detector_scores.parquet", index=False)
    write(sidd, "sati-siddhidatri-detector-scores",
          "Three Anomaly Detectors, Scored on Unseen Servers",
          "Per-minute scores from a learned and two statistical detectors, for fusion and calibration",
          "For every SMD server-minute: the score of Shailaputri (a gradient-boosted detector trained only on the "
          "*other* machine groups), of the largest robust z-score, and of per-machine PCA reconstruction error, with "
          "the anomaly label. Built for research on combining detectors and calibrating their probabilities.\n\n"
          "**Finding to beat:** Siddhidatri's logistic fusion matched Shailaputri alone on F1 (0.534 against 0.530) "
          "but raised false alarms from 4.0 to 47.9 per 1000; held to Shailaputri's false-alarm rate it still did "
          "not catch more. A fusion that wins here is an open result.\n\n" + licence_note,
          "other", ["computer science", "time series analysis", "anomaly detection"],
          [{"path": "detector_scores.parquet", "description": "One row per server-minute.",
            "schema": {"fields": [field("machine", "Server"), field("group", "Machine group"),
                                  field("minute", "Minute index", "integer"),
                                  field("shailaputri", "Learned detector's probability (trained without this group)", "number"),
                                  field("max_robust_z", "log1p of the largest robust z across metrics", "number"),
                                  field("pca", "log1p of PCA error relative to the machine's own quantile", "number"),
                                  field("anomaly", "1 if labelled anomalous", "integer")]}}])


# --- Chandraghanta and Kalaratri: benchmark definitions only ------------------

def benchmark_only(out: Path) -> None:
    models = ROOT / "docs" / "research" / "models"
    for name, slug, title, subtitle, files, body in (
        ("chandraghanta", "sati-chandraghanta-ids-split-benchmark", "Intrusion Detection: Unseen-Attack Splits",
         "Day splits for CIC-IDS2017 and the official UNSW-NB15 split, with per-family results",
         ["chandraghanta.results.json", "chandraghanta.md"],
         "How network intrusion detectors look when tested on attacks they have never seen. For CIC-IDS2017 the "
         "split is by day (train Monday–Wednesday, test Thursday–Friday), so every test attack family is unseen; on "
         "a random split the same model scores F1 0.997, on unseen days 0.453. This dataset holds the split "
         "definitions and every result per attack family. **The traffic itself is not redistributed** (its licence "
         "allows research use only): the example notebook attaches CIC-IDS2017 from its existing Kaggle copy."),
        ("kalaratri", "sati-kalaratri-log-anomaly-time-split", "Log Anomaly Detection: Time-Split Results",
         "Time-ordered splits for LogHub HDFS and BGL, with every detector's results",
         ["kalaratri.results.json", "kalaratri.md", "kalaratri-bgl.results.json", "kalaratri-bgl.md"],
         "Results and split definitions for log anomaly detection on LogHub HDFS (sessions) and BGL (time windows), "
         "split by time so the test set is the future. Kalaratri (Sati's log model) reaches F1 0.966 on HDFS and "
         "0.355 on BGL. **The logs themselves are not redistributed** (LogHub is for research or academic use "
         "only): the example notebook attaches them from their Kaggle copies."),
    ):
        folder = out / name
        folder.mkdir(parents=True, exist_ok=True)
        resources = []
        for f in files:
            src = models / f
            if src.exists():
                (folder / f).write_bytes(src.read_bytes())
                resources.append({"path": f, "description": "Generated results" if f.endswith(".json")
                                  else "The generated results table, as published"})
        write(folder, slug, title, subtitle, body, "CC-BY-4.0",
              ["computer science", "cybersecurity", "anomaly detection"], resources)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(".cache"))
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    steps = {"katyayani": lambda: katyayani(args.out),
             "brahmacharini": lambda: brahmacharini(args.out, args.cache / "corpus"),
             "skandamata": lambda: skandamata(args.out, args.cache / "corpus"),
             "kushmanda": lambda: kushmanda(args.out, args.cache / "corpus"),
             "smd": lambda: smd_sets(args.out, args.cache),
             "benchmarks": lambda: benchmark_only(args.out)}
    for name, step in steps.items():
        if args.only is None or name in args.only:
            step()
    print("digest", hashlib.sha256(str(sorted(p.name for p in args.out.rglob("*"))).encode()).hexdigest()[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
