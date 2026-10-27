"""Export ATT&CK's own technique → mitigation links for the API.

    python -m sati.serving.attackmap --cache ../../.cache/corpus --out ../../services/api/app/sati_models

Skandamata was trained on analysts' procedure write-ups, and a visitor's
question is worded differently ("ransomware encrypting our file shares"), so on
its own it can rank the wrong defences. Brahmacharini, which retrieves the
technique, reads such questions well. So the API chains them: Brahmacharini
finds the technique, these links (ATT&CK's `mitigates` relationships, the same
ground truth Skandamata is scored against) give its mitigations, and Skandamata
ranks them. Every recommendation then traces to a cited technique (rule 1).

No training: this is MITRE's data, reshaped. Sub-techniques with no links of
their own inherit their parent's, as in `sati.respond.data`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sati.embed.data import load
from sati.lm.corpus import ATTACK, _get
from sati.respond.data import mitigations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bundle = json.loads(_get(ATTACK, args.cache))
    items, by_technique = mitigations(bundle)
    stix_to_mitigation = {m.stix_id: m.attack_id for m in items}
    techniques, _ = load(args.cache)
    links = {t.attack_id: sorted(stix_to_mitigation[s] for s in by_technique.get(t.stix_id, ()))
             for t in techniques if by_technique.get(t.stix_id)}
    out = {"source": "MITRE ATT&CK enterprise, mitigates relationships", "techniques": len(links), "links": links}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "attack_mitigations.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(links)} techniques with mitigations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
