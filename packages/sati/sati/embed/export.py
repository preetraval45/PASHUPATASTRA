"""Export Brahmacharini for serving inside the API — no PyTorch, no NumPy.

    python -m sati.embed.export --cache .cache/corpus --out services/api/app/sati_models

The API runs on Lambda with a lean archive, so the served model is a smaller
version of the same design (fewer hash buckets, narrower) trained the same way,
then quantised to int8 with a scale per row. At query time the API hashes the
text, averages a few dozen rows, applies one small matrix and compares against
the knowledge base — a few hundred thousand multiply-adds, in pure Python.

The knowledge base is permissively licensed only: MITRE ATT&CK techniques and
mitigations, CAPEC attack patterns and CISA KEV entries (datasheets.md). Each
passage keeps its source and link, so every answer built from it can cite it.

Files written:
* `brahmacharini.json` — config, the projection, the bag's per-row scales
* `brahmacharini.bag`  — int8 bag rows, row-major
* `knowledge.json`     — passages: id, source, title, url, text
* `knowledge.vec`      — int8 passage embeddings with one scale each
"""

from __future__ import annotations

import argparse
import json
import random
import re
import struct
from pathlib import Path

import numpy as np
import torch

from sati.embed import data as d
from sati.embed.model import Encoder, info_nce
from sati.lm.corpus import ATTACK, CAPEC, KEV, _get

SERVE_BUCKETS = 1 << 15
WIDTH = 128
DIM = 96
EPOCHS = 10


def passages(cache: Path) -> list[dict]:
    out = []
    for url, source in ((ATTACK, "MITRE ATT&CK"), (CAPEC, "MITRE CAPEC")):
        bundle = json.loads(_get(url, cache))
        # CAPEC's mitigations have no id or link of their own; they are named "coa-<pattern>-<n>". Each is
        # filed under its attack pattern, so it can be cited (until 28 Oct they went out as "coa-1-0").
        patterns = {}
        for o in bundle["objects"]:
            ref = next((r for r in o.get("external_references", []) if r.get("external_id")), {})
            if o["type"] == "attack-pattern" and ref.get("external_id", "").startswith("CAPEC-"):
                patterns[ref["external_id"].removeprefix("CAPEC-")] = (o.get("name", ""), ref.get("url", ""))
        for o in bundle["objects"]:
            if o.get("revoked") or o.get("x_mitre_deprecated"):
                continue
            if o["type"] not in ("attack-pattern", "course-of-action"):
                continue
            text = d.clean(o.get("description", ""))
            if len(text) < 60:
                continue
            ref = next((r for r in o.get("external_references", []) if r.get("external_id")), {})
            kind = "mitigation" if o["type"] == "course-of-action" else "technique" if source == "MITRE ATT&CK" else "attack pattern"
            entry = {
                "id": ref.get("external_id", o["id"]),
                "source": source,
                "kind": kind,
                "title": o.get("name", ""),
                "url": ref.get("url", ""),
                "text": text[:900],
            }
            parent = re.fullmatch(r"coa-(\d+)-(\d+)", entry["title"]) if source == "MITRE CAPEC" else None
            if parent and parent.group(1) in patterns:
                name, link = patterns[parent.group(1)]
                entry.update(id=f"CAPEC-{parent.group(1)} mitigation {int(parent.group(2)) + 1}",
                             title=f"Mitigation for {name}", url=link)
            if not entry["url"]:
                continue  # nothing to cite
            out.append(entry)
    for v in json.loads(_get(KEV, cache)).get("vulnerabilities", []):
        out.append({
            "id": v["cveID"],
            "source": "CISA KEV",
            "kind": "exploited vulnerability",
            "title": v.get("vulnerabilityName", v["cveID"]),
            "url": f"https://nvd.nist.gov/vuln/detail/{v['cveID']}",
            "text": f"{v.get('shortDescription', '')} Required action: {v.get('requiredAction', '')}".strip()[:900],
        })
    return out


def train(cache: Path) -> Encoder:
    torch.manual_seed(7)
    random.seed(7)
    techniques, procedures = d.load(cache)
    index = {t.stix_id: i for i, t in enumerate(techniques)}
    train_set = procedures  # every source: this is the served model, not the evaluated one
    model = Encoder(dim=DIM, width=WIDTH, buckets=SERVE_BUCKETS)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    for epoch in range(EPOCHS):
        random.shuffle(train_set)
        for i in range(0, len(train_set), 128):
            seen, uniq = set(), []
            for p in train_set[i : i + 128]:
                if p.technique not in seen:
                    seen.add(p.technique)
                    uniq.append(p)
            if len(uniq) < 2:
                continue
            loss = info_nce(model([p.text for p in uniq]), model([techniques[index[p.technique]].text for p in uniq]))
            opt.zero_grad()
            loss.backward()
            opt.step()
        print(f"  epoch {epoch + 1}: loss {loss.item():.3f}")
    return model


def classifier(cache: Path, results: Path) -> dict:
    """The TF-IDF classifier served beside the encoder, fused with it as the test measured
    ("served design + pruned tf-idf (fused)" in brahmacharini.md).

    Trained on every procedure, as the served encoder is, then pruned to KEEP int8 weights per
    technique. The whole vocabulary and its idf are kept: TF-IDF divides by the norm over every
    feature, so dropping any would change the scores. `parity` holds texts and the top techniques
    with probabilities as numpy computes them; the API's pure-Python scorer is tested against it.
    """
    from sati.embed.metrics import prune, softmax
    from sati.embed.run import KEEP, fit_linear

    techniques, procedures = d.load(cache)
    index = {t.stix_id: i for i, t in enumerate(techniques)}
    vec, clf = fit_linear(procedures, [t.text for t in techniques], index)
    weights = prune(clf.coef_, KEEP)
    classes = []
    for row, cls in enumerate(clf.classes_):
        cols = np.flatnonzero(weights[row])
        scale = float(np.abs(weights[row, cols]).max() / 127.0) if len(cols) else 1.0
        classes.append({"id": techniques[cls].attack_id, "bias": round(float(clf.intercept_[row]), 6),
                        "scale": round(scale, 9), "features": cols.tolist(),
                        "weights": np.round(weights[row, cols] / scale).astype(int).tolist()})
    terms = sorted(vec.vocabulary_, key=vec.vocabulary_.get)
    samples = [p.text for p in procedures[:: max(1, len(procedures) // 12)]][:12]
    probs = softmax(np.asarray(vec.transform(samples) @ weights.T) + clf.intercept_)
    parity = [{"text": t, "top": [[techniques[clf.classes_[j]].attack_id, round(float(p[j]), 6)]
                                  for j in np.argsort(-p)[:5]]} for t, p in zip(samples, probs, strict=True)]
    weight = 0.8
    if results.exists():
        weight = json.loads(results.read_text(encoding="utf-8")).get("served", {}).get(
            "fusion_weight_by_validation", weight)
    return {"model": "sati-brahmacharini-classifier-v0", "keep": KEEP, "fusion_weight": weight,
            "terms": terms, "idf": [round(float(x), 6) for x in vec.idf_], "classes": classes, "parity": parity}


def quantise(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scale = np.abs(matrix).max(axis=1) / 127.0
    scale[scale == 0] = 1.0
    return np.round(matrix / scale[:, None]).astype(np.int8), scale.astype(np.float32)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=Path("../../results/brahmacharini/results.json"),
                        help="the evaluation run, for the fusion weight it chose on validation sources")
    parser.add_argument("--no-classifier", dest="classifier", action="store_false")
    args = parser.parse_args()

    model = train(args.cache).eval()
    bag = model.bag.weight.detach().numpy()
    q_bag, bag_scale = quantise(bag)

    kb = passages(args.cache)
    with torch.no_grad():
        vectors = torch.cat([model([f"{p['title']}. {p['text']}" for p in kb[i : i + 512]]) for i in range(0, len(kb), 512)]).numpy()
    q_kb, kb_scale = quantise(vectors)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "brahmacharini.bag").write_bytes(q_bag.tobytes())
    (args.out / "brahmacharini.json").write_text(json.dumps({
        "model": "sati-brahmacharini-serve-v0",
        "buckets": SERVE_BUCKETS,
        "width": WIDTH,
        "dim": DIM,
        "bag_scale": [round(float(s), 8) for s in bag_scale],
        "projection": [[round(float(x), 6) for x in row] for row in model.proj.weight.detach().numpy()],
        "bias": [round(float(x), 6) for x in model.proj.bias.detach().numpy()],
    }), encoding="utf-8")
    with (args.out / "knowledge.vec").open("wb") as handle:
        handle.write(struct.pack("<II", len(kb), DIM))
        handle.write(kb_scale.astype("<f4").tobytes())
        handle.write(q_kb.tobytes())
    (args.out / "knowledge.json").write_text(json.dumps(kb, ensure_ascii=False), encoding="utf-8")
    print(f"exported: {len(kb)} passages, bag {q_bag.nbytes / 1e6:.1f} MB")
    if args.classifier:
        served = classifier(args.cache, args.results)
        (args.out / "technique_classifier.json").write_text(json.dumps(served, ensure_ascii=False), encoding="utf-8")
        print(f"exported: classifier over {len(served['classes'])} techniques, {len(served['terms']):,} terms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
