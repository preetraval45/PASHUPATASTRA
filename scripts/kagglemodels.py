"""Assemble the nine public Kaggle Models, one per Sati model, from the served artefacts.

    python scripts/kagglemodels.py --out build/kaggle-models [--only katyayani ...]

Each model folder gets `model-metadata.json` (the model card) and an instance
folder with the files and `model-instance-metadata.json` (format, usage,
licence, training data). The files are exactly what the API serves on AWS, so
the published model is the deployed one. Boosters are JSON for
`pashupatastra.trees` (plain Python); the encoders are int8 for a pure-Python
or numpy forward pass. Licences follow docs/research/datasheets.md:
Apache-2.0 where every source allows it, CC BY-NC-SA 4.0 (research use only)
for models trained on research-only data.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVED = ROOT / "services" / "api" / "app" / "sati_models"
OWNER = "preetraval4518071604"
REPO = "https://github.com/preetraval45/PASHUPATASTRA"

TREES_USAGE = (
    "# Model Format\nA LightGBM booster exported as JSON for `pashupatastra.trees`: every tree's splits and leaf "
    "values, nothing executable. Missing values follow LightGBM's rules; a parity test checks the scores equal "
    "LightGBM's.\n\n# Model Usage\n```python\nimport json\nfrom pashupatastra import trees  # pip install from "
    f"{REPO} (packages/core)\nmodel = json.load(open('MODEL.json'))\nscore = trees.predict(model, trees.row_from(model, "
    "features))\n```\n"
)


def card(job: str, how: str, data: str, results: str, licence_note: str) -> str:
    return (f"# Model Summary\n{job}\n\nPart of **Sati**, the investigation agent of [Pashupatastra]({REPO}): nine "
            "models, each named for a form of Navadurga and each doing the job that fits its form. Sati proposes; a "
            "policy engine and a person authorise every action.\n\n# Model Characteristics\n" + how +
            "\n\n# Data Overview\n" + data + "\n\n# Evaluation Results\n" + results +
            "\n\nEvery number is regenerated from committed results; the split keeps the test honest (held out by "
            "group, source, system, day or time, never a leaking random split).\n\n# Licence\n" + licence_note)


MODELS = {
    "katyayani": {
        "title": "Katyayani: Root Cause Ranking",
        "subtitle": "Ranks the services of an incident so the root cause comes first",
        "files": {"katyayani.json": "katyayani.json"},
        "dataset": "sati-katyayani-live-fault-injections",
        "licence": "Apache 2.0",
        "description": card(
            "Given an incident in a microservice system, Katyayani ranks every service by how likely it is to be "
            "the root cause, from event-level evidence: how far each service's metrics moved, when it went "
            "anomalous, and its place in the call graph.",
            "LightGBM LambdaRank over 17 event-level features. Trained on real fault injections from RCAEval "
            "(Online Boutique, Sock Shop) and the project's live Kubernetes stack, with one incident in ten kept "
            "aside; the file ships those incidents so the model can be tried on cases it never saw.",
            "RCAEval (MIT) and the project's own live fault injections (CC-BY-4.0).",
            "Each system held out in turn: RCA@1 0.900 on the live stack, 0.849 on Online Boutique, 0.894 on Sock "
            "Shop, against 0.265, 0.490 and 0.265 for the same design trained on synthetic incidents. On a "
            "pre-declared RCAEval sample the series-feature design names the root first in 0.940 of cases, against "
            "0.550 for llama3 and 0.510 for qwen2.5:7b given the same evidence.",
            "Apache-2.0. RCAEval is MIT."),
        "usage": TREES_USAGE.replace("MODEL.json", "katyayani.json").replace(
            "model = json.load", "served = json.load").replace(
            "score = trees.predict(model", "model = served['booster']\nscore = trees.predict(model"),
    },
    "brahmacharini": {
        "title": "Brahmacharini: Behaviour to ATT&CK Technique",
        "subtitle": "Finds the ATT&CK technique an observed attacker behaviour belongs to",
        "files": {"brahmacharini.json": "brahmacharini.json", "brahmacharini.bag": "brahmacharini.bag",
                  "knowledge.json": "knowledge.json", "knowledge.vec": "knowledge.vec",
                  "technique_classifier.json": "technique_classifier.json"},
        "dataset": "sati-brahmacharini-attack-behaviour-to-technique",
        "licence": "Apache 2.0",
        "description": card(
            "A dual encoder that maps an observed behaviour and every ATT&CK technique into one space, so the "
            "nearest technique is the answer; it also retrieves the knowledge-base passage Sati cites.",
            "Hashed word unigrams and bigrams → mean of int8 embedding rows → linear projection, L2-normalised. "
            "Trained contrastively (InfoNCE). Small enough to run in pure Python in a Lambda function.",
            "MITRE ATT&CK enterprise procedure examples, split by source; the served knowledge base holds ATT&CK, "
            "CAPEC and CISA KEV passages.",
            "On attackers never seen in training: Recall@1 0.614, Recall@10 0.854, against 0.268 and 0.580 for "
            "BM25. The served design (int8, smaller) reaches 0.556 alone and 0.650 fused with the TF-IDF "
            "classifier in technique_classifier.json, which is what answers 'which technique is this?'.", "Apache-2.0. ATT&CK content is © MITRE, used under its terms with attribution."),
        "usage": "# Model Format\nInt8 bag rows (`brahmacharini.bag`) with per-row scales and the projection "
                 "(`brahmacharini.json`); the knowledge base and its int8 vectors.\n\n# Model Usage\nHash the "
                 "text's words and bigrams with CRC32 into `buckets`, average those rows times their scales, "
                 "apply the projection and bias, L2-normalise, and compare by cosine. Reference implementation: "
                 f"`services/api/app/engines/providers/sati.py` in {REPO}.\n",
    },
    "skandamata": {
        "title": "Skandamata: Mitigation Recommender",
        "subtitle": "Recommends the ATT&CK mitigations that defend against an attacker behaviour",
        "files": {"skandamata.json": "skandamata.json", "skandamata.bag": "skandamata.bag",
                  "attack_mitigations.json": "attack_mitigations.json",
                  "mitigation_classifier.json": "mitigation_classifier.json"},
        "dataset": "sati-skandamata-attack-behaviour-to-mitigations",
        "licence": "Apache 2.0",
        "description": card(
            "Ranks the 44 ATT&CK enterprise mitigations for an observed attacker behaviour. In Sati it is chained "
            "with Brahmacharini: the technique Brahmacharini finds gives ATT&CK's own mitigations, and Skandamata "
            "orders them.",
            "Hashed n-grams → mean of int8 embedding rows → one ReLU layer → a probability per mitigation. "
            "Multi-label, trained with binary cross-entropy. The export checks it ranks as PyTorch did.",
            "ATT&CK procedure examples with every mitigation linked to their technique, split by source.",
            "First recommendation right 0.787 of the time on unseen attackers, against 0.537 for BM25 over "
            "techniques and 0.232 for recommending the most common mitigations. A TF-IDF classifier does better "
            "(0.827); pruned to int8 as served (mitigation_classifier.json) it ranks the list better (nDCG@10 "
            "0.850 against 0.839), so the API orders mitigations by it.",
            "Apache-2.0. ATT&CK content is © MITRE, used under its terms with attribution."),
        "usage": "# Model Format\nInt8 bag rows plus two float layers in `skandamata.json`; "
                 "`attack_mitigations.json` holds ATT&CK's technique → mitigation links.\n\n# Model Usage\nHash, "
                 "average rows, ReLU layer, sigmoid per mitigation. Reference implementation: the `Skandamata` "
                 f"class in `services/api/app/engines/providers/sati.py` in {REPO}.\n",
    },
}

RESEARCH_NOTE = ("**Research use only, not for commercial use (CC BY-NC-SA 4.0).** Trained on data whose terms "
                 "allow research use only; released on that basis by the owner's decision (27 Oct 2026).")
MODELS["kalaratri"] = {
    "title": "Kalaratri: Log Anomaly Detector", "subtitle": "Flags failing sessions from the counts of their log events",
    "files": {"kalaratri.json": "kalaratri.json"}, "dataset": "sati-kalaratri-log-anomaly-time-split",
    "licence": "CC BY-NC-SA 4.0",
    "description": card(
        "Reads a log session (an HDFS block's events) as counts of event templates and says whether it is failing.",
        "LightGBM over event-template counts, trained on the earlier 60% of sessions in log order, with the "
        "threshold chosen on the next 20%; exported as JSON with its event vocabulary.",
        "LogHub HDFS (research or academic use only).",
        "On the later 20% of sessions: F1 0.966, against 0.866 for the classic PCA detector. On BGL, where "
        "failures are rarer, the same design reaches 0.355: HDFS alone flatters log anomaly detection.",
        RESEARCH_NOTE),
    "usage": TREES_USAGE.replace("MODEL.json", "kalaratri.json") + "\nFeatures are counts of the event templates "
             "in `vocabulary`, in that order.\n",
}
MODELS["chandraghanta"] = {
    "title": "Chandraghanta: Network Intrusion Detector",
    "subtitle": "Flags malicious network flows, tested on attack families it never saw",
    "files": {"chandraghanta.json": "chandraghanta.json"}, "dataset": "sati-chandraghanta-ids-split-benchmark",
    "licence": "CC BY-NC-SA 4.0",
    "description": card(
        "Classifies a network flow (CICFlowMeter features) as benign or attack.",
        "LightGBM with class weighting, the threshold chosen on a validation slice of the training days; "
        "exported as JSON.",
        "CIC-IDS2017 split by day: trained Monday to Wednesday (research use only).",
        "On Thursday and Friday, where every attack family is unseen, F1 0.453; on a random split the same model "
        "scores 0.997. It catches web attacks it never saw and misses port scans and bots.",
        RESEARCH_NOTE),
    "usage": TREES_USAGE.replace("MODEL.json", "chandraghanta.json"),
}

SMD_NOTE = "Apache-2.0. Trained on the Server Machine Dataset (SMD, MIT licence; Su et al., KDD 2019)."
for form, title, subtitle, job, results in (
    ("shailaputri", "Shailaputri: Server Anomaly Detector", "Flags anomalous minutes across a server's metrics",
     "Flags the minutes a server behaves abnormally, from causal per-minute features aggregated across its "
     "metrics.",
     "Each machine group held out in turn: F1 0.556 with 4.6 false alarms per 1000 minutes, against 0.419 and "
     "86.6 for per-machine PCA."),
    ("mahagauri", "Mahagauri: Recovery Verifier", "Says when a server incident is really over",
     "Answers once a minute whether the server has recovered, and declares the incident over once recovery has "
     "held long enough. The dangerous error is declaring it over too early.",
     "On unseen machine groups, 0.021 of incidents declared over too early (budget 0.05), but only 0.095 of "
     "recoveries confirmed: safe, rarely decisive."),
    ("siddhidatri", "Siddhidatri: Detector Fusion", "Fuses three anomaly detectors into one calibrated probability",
     "Combines Shailaputri with two statistical detectors (robust z, PCA) by logistic regression into one "
     "probability per minute.",
     "F1 0.537 against Shailaputri's 0.539, with false alarms of 47.8 against 3.8 per 1000: published as an "
     "honest negative, and as the baseline for better fusion."),
):
    MODELS[form] = {
        "title": title, "subtitle": subtitle, "files": {f"{form}.json": f"smd:{form}"},
        "dataset": {"shailaputri": "sati-shailaputri-smd-server-anomalies", "mahagauri": "sati-mahagauri-server-recovery",
                    "siddhidatri": "sati-siddhidatri-detector-scores"}[form],
        "licence": "Apache 2.0",
        "description": card(job, "LightGBM (gradient-boosted trees), exported as JSON for plain-Python scoring; "
                            "trained on two SMD machine groups, so the third can be used to test it.",
                            "SMD: 28 real servers, 38 metrics each, labelled anomalies.", results, SMD_NOTE),
        "usage": TREES_USAGE.replace("MODEL.json", f"{form}.json"),
    }


def assemble(form: str, spec: dict, out: Path) -> None:
    folder, instance = out / form, out / form / "instance"
    instance.mkdir(parents=True, exist_ok=True)
    for name, source in spec["files"].items():
        if source.startswith("smd:"):
            bundle = json.loads((SERVED / "smd.json").read_text(encoding="utf-8"))["models"]
            key = source.split(":")[1]
            payload = {"siddhidatri": {"fusion": bundle["siddhidatri"], "learned_input": bundle["siddhidatri_input"]},
                       }.get(key, bundle[key])
            (instance / name).write_text(json.dumps(payload), encoding="utf-8")
        else:
            shutil.copy(SERVED / source, instance / name)
    slug = f"sati-{form}"
    (folder / "model-metadata.json").write_text(json.dumps({
        "ownerSlug": OWNER, "title": spec["title"], "slug": slug, "subtitle": spec["subtitle"], "isPrivate": False,
        "description": spec["description"], "publishTime": "", "provenanceSources": REPO}, indent=1), encoding="utf-8")
    (instance / "model-instance-metadata.json").write_text(json.dumps({
        "ownerSlug": OWNER, "modelSlug": slug, "instanceSlug": "default", "framework": "other",
        "overview": spec["subtitle"], "usage": spec["usage"], "licenseName": spec["licence"], "fineTunable": False,
        "trainingData": [f"{OWNER}/{spec['dataset']}"], "modelInstanceType": "Unspecified",
        "baseModelInstanceId": 0, "externalBaseModelUrl": ""}, indent=1), encoding="utf-8")
    print("assembled", form, sorted(p.name for p in instance.iterdir()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    for form, spec in MODELS.items():
        if args.only and form not in args.only:
            continue
        missing = [s for s in spec["files"].values() if not (SERVED / s.split(":")[0].replace("smd", "smd.json")
                                                              if s.startswith("smd:") else SERVED / s).exists()]
        if missing:
            print(f"skip {form}: not exported yet ({missing})")
            continue
        assemble(form, spec, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
