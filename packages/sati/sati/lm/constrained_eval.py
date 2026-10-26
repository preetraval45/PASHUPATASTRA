"""Measure constrained decoding on Kushmanda v2's held-out ID questions (RP-44).

    python -m sati.lm.constrained_eval --model /kaggle/input/... --cache cache/corpus --out out

The questions are the same as `train.py`'s evaluation: the seed-7 sample of
the held-out set, restricted to the questions whose answer is one identifier
(technique lookup, and behaviour → technique). Each question is answered
twice by the same model:

* **free:** greedy decoding, exactly as reported in `models/kushmanda.md`;
* **constrained:** the model answers freely first. If it abstains, the
  abstention stands, so its ability to decline is kept. Otherwise the
  identifier is decoded constrained to those in the context, and its passage
  is cited (`sati.lm.constrained`).

Both are scored by `sati.lm.evaluate.score`, so the comparison is like for
like. Runs on Kaggle with the private model attached (`kaggle/kushmanda-constrained`).
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import torch

from sati.lm import evaluate, sft
from sati.lm.constrained import constrained_id
from sati.lm.model import Config, Kushmanda
from sati.lm.train import answer

KINDS = ("lookup", "classify")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="folder holding kushmanda-v2.pt and tokenizer.json")
    parser.add_argument("--cache", type=Path, default=Path("cache/corpus"))
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--eval-questions", type=int, default=1200)
    args = parser.parse_args()

    from tokenizers import Tokenizer

    started = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt_path = next(args.model.rglob("kushmanda-v2.pt"))
    tok = Tokenizer.from_file(str(next(args.model.rglob("tokenizer.json"))))
    ckpt = torch.load(ckpt_path, map_location=device)
    model = Kushmanda(Config(**ckpt["config"])).to(device)
    model.load_state_dict(ckpt["state"])
    model.eval()

    _, test = sft.build(args.cache)
    questions = random.Random(7).sample(test, min(len(test), args.eval_questions))
    questions = [q for q in questions if q["kind"] in KINDS]

    @torch.no_grad()
    def next_scores(ids: list[int]):
        window = torch.tensor([ids[-model.cfg.context:]], device=device)
        return model(window)[0][0, -1].float().cpu().numpy()

    free, constrained = [], []
    for q in questions:
        got = answer(model, tok, q["q"], device, 24, q["context"])
        free.append(got)
        if evaluate.parse(got)[2]:
            constrained.append(got)  # the model declined: keep it
            continue
        prompt, _ = sft.format_pair(q["q"], "", q["context"])
        ids = tok.encode(prompt).ids[-(model.cfg.context - 16):]
        constrained.append(constrained_id(next_scores, lambda x: tok.decode(x), ids, q["context"]))

    results = {
        "model": "sati-kushmanda-v2",
        "questions": len(questions),
        "kinds": list(KINDS),
        "free": evaluate.score(questions, free),
        "constrained": evaluate.score(questions, constrained),
        "lexical baseline": evaluate.score(questions, [evaluate.lexical(q) for q in questions]),
        "valid_outputs": {
            "free": round(sum(bool(evaluate.first_id(a)) or evaluate.parse(a)[2] for a in free) / len(free), 4),
            "constrained": round(sum(bool(evaluate.first_id(a)) or evaluate.parse(a)[2] for a in constrained)
                                 / len(constrained), 4),
        },
        "examples": [{"question": q["q"][:160], "expected": q["a"], "free": f, "constrained": c}
                     for q, f, c in list(zip(questions, free, constrained, strict=True))[:8]],
        "device": device,
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "constrained.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("free", "constrained", "lexical baseline", "valid_outputs")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
