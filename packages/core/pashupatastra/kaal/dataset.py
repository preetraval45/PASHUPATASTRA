"""Kaal dataset v1: splits, a contamination guard and a manifest (RP-18).

    python -m pashupatastra.kaal.dataset --n 50000 --seed 1 --manifest docs/research/datasets/kaal-v1.json

**Splits,** decided by rules fixed here, before any training:

* **test-ood-fault:** every incident whose fault type is held out
  (`HELD_OUT_FAULTS`). `cpu_saturation` is an unseen fault in a seen category
  (compute keeps `memory_leak`). `consumer_lag` is an unseen category (queue).
* **test-ood-topology:** every remaining incident whose topology *shape*
  hashes into one bucket in ten. Shape means the structure (layers, store
  kinds, call degrees), not names, so these are graphs the model never trains
  on.
* **train / validation / test-id:** the rest, 80 / 10 / 10, by a hash of the
  incident id.

**Contamination guard.** The run fails if:

* any incident's topology matches the PIB reference stack, or
* any training incident's structural signature (topology shape, fault, and
  the ordered sequence of layer, metric, direction and rounded σ) also
  appears in a test split.

Two checks are named in the manifest as **pending**, because neither source
exists in this repository as a graph yet: the 20 labelled incidents (RP-13)
and RCAEval's three topologies.

**Manifest.** The generator version, seed, n, rules, counts per split, the
SHA-256 of each split's sorted id list, the guard's results, and simple
realism statistics (anomalous services per incident, propagation depth). It
is committed, and a training run reads its split from it, never recomputes
one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from pashupatastra.kaal.generator import VERSION, Incident, callers_by_distance, incident

HELD_OUT_FAULTS = ("cpu_saturation", "consumer_lag")
OOD_TOPOLOGY_BUCKET = 0  # shape hash mod 10
PIB_REFERENCE_SERVICES = 5  # benchmark/harness/stack.py: five services, no declared call graph
SPLITS = ("train", "validation", "test-id", "test-ood-topology", "test-ood-fault")


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def shape(inc: Incident) -> str:
    """Topology structure without names: each service's layer, kind and call degrees."""
    out_deg, in_deg = Counter(a for a, _ in inc.calls), Counter(b for _, b in inc.calls)
    nodes = sorted((s.layer, s.kind.value, out_deg[s.name], in_deg[s.name]) for s in inc.services)
    return hashlib.sha256(json.dumps(nodes).encode()).hexdigest()[:16]


def signature(inc: Incident) -> str:
    """Structure plus what happened: shape, fault, and the ordered event pattern."""
    layer = {s.name: s.layer for s in inc.services}
    pattern = []
    for e in inc.events:
        p = e.payload
        metric = getattr(p, "name", p.kind)
        sigma = getattr(p, "deviation_sigma", None)
        pattern.append((layer[e.entity_ref.id], metric, 0 if sigma is None else int(round(sigma))))
    return hashlib.sha256(json.dumps([shape(inc), inc.label["fault_type"], pattern]).encode()).hexdigest()[:20]


def split_of(inc: Incident) -> str:
    if inc.label["fault_type"] in HELD_OUT_FAULTS:
        return "test-ood-fault"
    if _h(shape(inc)) % 10 == OOD_TOPOLOGY_BUCKET:
        return "test-ood-topology"
    bucket = _h(inc.id) % 10
    return "train" if bucket < 8 else "validation" if bucket == 8 else "test-id"


def depth(inc: Incident) -> int:
    """Propagation depth: hops from the root to the furthest affected caller."""
    root = inc.label["root_service"]
    if root is None:
        return 0
    hops = dict(callers_by_distance(str(root), inc.calls))
    return max((hops.get(s, 0) for s in inc.label["affected"]), default=0)  # type: ignore[union-attr]


def build(n: int, seed: int) -> dict:
    """Assign every incident, then drop from each test split any incident whose
    signature also occurs in training: an exact structural repeat measures
    memory, not generalisation. The count dropped is reported, never hidden."""
    rows = []
    pib_matches, anomalous, depths = 0, Counter(), Counter()
    for i in range(n):
        inc = incident(seed, i)
        rows.append((split_of(inc), inc.id, signature(inc), str(inc.label["outcome"])))
        if len(inc.services) == PIB_REFERENCE_SERVICES and not inc.calls:
            pib_matches += 1
        anomalous[len(inc.label["affected"])] += 1  # type: ignore[arg-type]
        depths[depth(inc)] += 1
    train_sigs = {sig for s, _, sig, _ in rows if s == "train"}
    removed = Counter(s for s, _, sig, _ in rows if s.startswith("test") and sig in train_sigs)
    kept = [r for r in rows if not (r[0].startswith("test") and r[2] in train_sigs)]
    ids: dict[str, list[str]] = {s: [] for s in SPLITS}
    outcomes: dict[str, Counter] = {s: Counter() for s in SPLITS}
    sigs: dict[str, set[str]] = {s: set() for s in SPLITS}
    for s, inc_id, sig, outcome in kept:
        ids[s].append(inc_id)
        outcomes[s][outcome] += 1
        sigs[s].add(sig)
    leaks = {t: len(sigs["train"] & sigs[t]) for t in SPLITS if t.startswith("test")}
    return {
        "dataset": "kaal-v1",
        "generator": VERSION,
        "seed": seed,
        "n": n,
        "rules": {
            "held_out_faults": list(HELD_OUT_FAULTS),
            "ood_topology": f"sha256(shape) mod 10 == {OOD_TOPOLOGY_BUCKET}, after held-out faults",
            "in_distribution": "sha256(incident id) mod 10: 0-7 train, 8 validation, 9 test-id",
        },
        "splits": {s: {"incidents": len(ids[s]), "outcomes": dict(sorted(outcomes[s].items())),
                       "ids_sha256": hashlib.sha256("\n".join(sorted(ids[s])).encode()).hexdigest()}
                   for s in SPLITS},
        "guard": {
            "pib_reference_topology_matches": pib_matches,
            "removed_from_tests_as_repeats_of_training": {t: removed.get(t, 0) for t in SPLITS if t.startswith("test")},
            "train_signatures_also_in": leaks,
            "passed": pib_matches == 0 and not any(leaks.values()),
            "pending": ["the 20 labelled incidents (RP-13): not yet written",
                        "RCAEval's three topologies: not in this repository as graphs"],
        },
        "realism": {
            "anomalous_services_per_incident": {str(k): v for k, v in sorted(anomalous.items())},
            "propagation_depth": {str(k): v for k, v in sorted(depths.items())},
            "compared_with_real": "pending RP-19 (fault-injected cluster runs) and an RCAEval comparison",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--manifest", type=Path, default=Path("kaal-v1.json"))
    parser.add_argument("--check", action="store_true",
                        help="regenerate and fail if the committed manifest differs (CI)")
    args = parser.parse_args()
    manifest = build(args.n, args.seed)
    if args.check:
        committed = json.loads(args.manifest.read_text(encoding="utf-8"))
        same = committed == manifest
        print("manifest matches the generator" if same else
              "manifest differs: the generator changed. Regenerate deliberately, and know that every split moved")
        return 0 if same and manifest["guard"]["passed"] else 1
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for s, v in manifest["splits"].items():
        print(f"  {s:18} {v['incidents']:>6}  {v['outcomes']}")
    print(f"guard passed: {manifest['guard']['passed']}  {manifest['guard']['train_signatures_also_in']}")
    return 0 if manifest["guard"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
