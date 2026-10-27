"""Draw the IEEE paper's new figures, in the style of its Fig. 1 (black on white, Times, grey for gates).

    python scripts/ieeefigures.py

Writes `docs/research/figures/`:

* `nine-models.png` — where each of the nine Sati models works in the incident loop. Job first, name
  second (adr/Navadurga). Dharma, the gate, has no model.
* `rq5-rca.png` — RQ5: share of the 100 pre-declared RCAEval cases each diagnoser ranks right, with
  95% Wilson intervals, read from the committed results file.

`scripts/ieeeupdate.py` embeds both as tracked insertions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "research" / "figures"
WEB = ROOT / "apps" / "web" / "lib" / "models"
GATE = "#e0e0e0"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                     "svg.fonttype": "none"})

# (stage, detail, gate?, [(job, model), ...])
LOOP = [
    ("Telemetry and threat feeds", "metrics, logs, flows, alerts", False, []),
    ("Drishti: perception", "one event model with provenance", False,
     [("Server metric anomalies", "Shailaputri"), ("Log session anomalies", "Kalaratri"),
      ("Network intrusion", "Chandraghanta")]),
    ("Correlation", "graph adjacency AND time", False, [("Fuse the three detectors", "Siddhidatri")]),
    ("Sati with Buddhi and Smriti", "hypotheses that cite records", False,
     [("Root-cause service", "Katyayani"), ("Behaviour to ATT&CK technique", "Brahmacharini"),
      ("Answer from cited passages", "Kushmanda")]),
    ("Recommendation", "ranked actions, each with rollback", False, [("Mitigations for the technique", "Skandamata")]),
    ("Dharma: policy verdict", "no model: deterministic gate", True, []),
    ("Astra: execution", "needs a live verdict; dry run default", False, []),
    ("Verification", "windowed comparison to expected state", False, [("Is the incident over?", "Mahagauri")]),
]


def nine_models(path: Path) -> None:
    """Drawn at the paper's column width (3.5 in), so the type prints at its stated size."""
    unit, box_h, lone = 0.30, 0.24, 0.40  # inches: a model row, a box, a stage with no model
    spans = [len(m) * unit if m else lone for *_, m in LOOP]
    height = sum(spans) + 0.1
    fig = plt.figure(figsize=(3.5, height))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 3.5)
    ax.set_ylim(0, height)
    ax.axis("off")
    left, width, right, rwidth = 0.04, 1.72, 1.92, 1.54
    y, prev_bottom = height - 0.05, None
    for (stage, detail, gate, models), span in zip(LOOP, spans, strict=True):
        mid = y - span / 2
        ax.add_patch(Rectangle((left, mid - box_h / 2), width, box_h, facecolor=GATE if gate else "white",
                               edgecolor="black", linewidth=0.7))
        cx = left + width / 2
        ax.text(cx, mid + 0.045, stage, ha="center", va="center", fontsize=6.5, fontweight="bold")
        ax.text(cx, mid - 0.06, detail, ha="center", va="center", fontsize=5.5)
        if prev_bottom is not None:
            ax.add_patch(FancyArrowPatch((cx, prev_bottom), (cx, mid + box_h / 2), arrowstyle="-|>",
                                         mutation_scale=5, linewidth=0.7, color="black", shrinkA=0, shrinkB=0))
        for k, (job, name) in enumerate(models):
            my = y - unit * (k + 0.5)
            ax.add_patch(Rectangle((right, my - box_h / 2), rwidth, box_h, facecolor="white", edgecolor="black",
                                   linewidth=0.6))
            ax.text(right + rwidth / 2, my + 0.045, job, ha="center", va="center", fontsize=6, fontweight="bold")
            ax.text(right + rwidth / 2, my - 0.06, name, ha="center", va="center", fontsize=5.5, style="italic")
            elbow = (left + width + right) / 2
            ax.plot([left + width, elbow, elbow, right], [mid, mid, my, my], color="black", linewidth=0.5)
        prev_bottom = mid - box_h / 2
        y -= span
    fig.savefig(path, dpi=600)
    plt.close(fig)


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def rq5(path: Path) -> None:
    d = json.loads((WEB / "rcaeval-diagnosis.results.json").read_text(encoding="utf-8"))
    n = d["cases"]
    names = {"katyayani": "Katyayani (trained on other systems)", "loudest": "Loudest service (no learning)",
             "llm:llama3": "Llama 3 8B", "llm:qwen2.5:7b": "Qwen2.5 7B",
             "sati-kaal": "Simulator-trained ranker"}
    keys = sorted(names, key=lambda k: d["rca@1"][k])
    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    for i, k in enumerate(keys):
        p = d["rca@1"][k]
        lo, hi = wilson(p, n)
        ax.barh(i, p, color=GATE if k != "katyayani" else "#404040", edgecolor="black", linewidth=0.6, height=0.62)
        ax.plot([lo, hi], [i, i], color="black", linewidth=0.9)
        ax.text(hi + 0.02, i, f"{p:.2f}", va="center", fontsize=7)
    ax.set_yticks(range(len(keys)), [names[k] for k in keys], fontsize=7)
    ax.set_xlim(0, 1.12)
    ax.spines["bottom"].set_bounds(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "0.25", "0.5", "0.75", "1"], fontsize=7)
    ax.set_xlabel(f"Root cause ranked first ({n} cases, 95% CI)", fontsize=7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout(pad=0.4)
    fig.subplots_adjust(right=0.97)
    fig.savefig(path, dpi=600)
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    nine_models(OUT / "nine-models.png")
    rq5(OUT / "rq5-rca.png")
    print("wrote", OUT / "nine-models.png", OUT / "rq5-rca.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
