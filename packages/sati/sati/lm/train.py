"""Train Kushmanda end to end: data → tokenizer → pretraining → instruction tuning → evaluation.

    python -m sati.lm.train --out results/kushmanda             # on a GPU
    python -m sati.lm.train --out /tmp/k --tiny                 # minute-long smoke run, CPU

v2 (26 Oct), after v1 overfitted by step 400 of 8,000 (its 34M parameters
memorised a 1.1M-token corpus) and scored zero on held-out questions asked
without context:

* NVD CVE descriptions added, about 20x the corpus.
* A smaller model (about 17M parameters) with dropout.
* Instruction tuning is grounded: answer from the passages given, cite one,
  or abstain (`sft.py`). It is scored against a lexical baseline and chance
  (`evaluate.py`).

1. **Data.** Build the corpus (`corpus.py`), clean and deduplicate it
   (`clean.py`), split by document — 5% held out.
2. **Tokenizer.** Byte-level BPE trained on the training documents only, with
   chat special tokens; tokens per held-out line compared against GPT-2's.
3. **Pretraining.** Next-token prediction. AdamW (β2 0.95, weight decay on
   matrices only), linear warmup then cosine decay, gradient clipping,
   gradient accumulation, and bf16/fp16 autocast on a GPU. Validation loss is
   checked through training and the best checkpoint is kept.
4. **Instruction tuning (SFT).** Question/answer pairs from the structured
   sources (`sft.py`), loss on the answer only, held out by entity.
5. **Evaluation.** Held-out bits per byte, which compares across tokenizers.
   On held-out entities: answer loss, plus `evaluate.score` for the model, the
   lexical baseline and chance.

Weights are Apache-2.0 eligible: every source allows it (datasheets.md).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import torch

from sati.lm import corpus as corpus_mod
from sati.lm import evaluate, sft
from sati.lm.model import Config, Kushmanda

SPECIAL = ["<|doc|>", sft.USER, sft.ASSISTANT, sft.END]
PROMPTS = (
    "Credential stuffing is",
    "To contain a host that is beaconing to a command-and-control server,",
    "T1566 Phishing",
)


def train_tokenizer(texts: list[str], vocab_size: int):
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

    tok = Tokenizer(models.BPE(unk_token=None))
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=vocab_size, special_tokens=SPECIAL,
                                  initial_alphabet=pre_tokenizers.ByteLevel.alphabet())
    tok.train_from_iterator(texts, trainer=trainer)
    return tok


def tokens_per_line(encode, lines: list[str]) -> float:
    return round(sum(len(encode(line)) for line in lines) / max(1, len(lines)), 2)


def gpt2_tokens_per_line(lines: list[str]) -> float | None:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("gpt2")
        return tokens_per_line(enc.encode, lines)
    except Exception:  # noqa: BLE001 — a missing comparison is reported as absent
        return None


def encode_docs(tok, docs: list[dict]) -> np.ndarray:
    sep = tok.token_to_id("<|doc|>")
    ids: list[int] = []
    for doc in docs:
        ids.extend(tok.encode(doc["text"]).ids)
        ids.append(sep)
    return np.array(ids, dtype=np.int32)


def lm_batch(data: np.ndarray, context: int, size: int, rng: np.random.Generator, device: str):
    starts = rng.integers(0, len(data) - context - 1, size)
    x = np.stack([data[s : s + context] for s in starts]).astype(np.int64)
    y = np.stack([data[s + 1 : s + 1 + context] for s in starts]).astype(np.int64)
    return torch.from_numpy(x).to(device), torch.from_numpy(y).to(device)


def sft_encode(tok, pairs: list[dict], context: int) -> list[tuple[list[int], list[int]]]:
    out = []
    for p in pairs:
        prompt, answer = sft.format_pair(p["q"], p["a"], p.get("context"))
        pi, ai = tok.encode(prompt).ids, tok.encode(answer).ids
        # Too long: drop the start of the prompt, never the answer.
        ids = (pi + ai)[-(context + 1):]
        mask = ([0] * len(pi) + [1] * len(ai))[-(context + 1):]
        if sum(mask[1:]) > 0:
            out.append((ids, mask))
    return out


def sft_batch(rows: list[tuple[list[int], list[int]]], device: str, pad: int):
    length = max(len(ids) for ids, _ in rows)
    x = torch.full((len(rows), length - 1), pad, dtype=torch.long)
    y = torch.full((len(rows), length - 1), pad, dtype=torch.long)
    m = torch.zeros((len(rows), length - 1), dtype=torch.long)
    for i, (ids, mask) in enumerate(rows):
        n = len(ids) - 1
        x[i, :n] = torch.tensor(ids[:-1])
        y[i, :n] = torch.tensor(ids[1:])
        m[i, :n] = torch.tensor(mask[1:])
    return x.to(device), y.to(device), m.to(device)


def optimiser(model: torch.nn.Module, lr: float) -> torch.optim.AdamW:
    decay = [p for n, p in model.named_parameters() if p.dim() >= 2]
    no_decay = [p for n, p in model.named_parameters() if p.dim() < 2]
    return torch.optim.AdamW([{"params": decay, "weight_decay": 0.1}, {"params": no_decay, "weight_decay": 0.0}],
                             lr=lr, betas=(0.9, 0.95))


def schedule(step: int, total: int, peak: float, warmup: int) -> float:
    if step < warmup:
        return peak * (step + 1) / warmup
    progress = (step - warmup) / max(1, total - warmup)
    return peak * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, progress))))


@torch.no_grad()
def held_out_loss(model, data: np.ndarray, context: int, device: str, autocast, limit: int = 120) -> float:
    model.eval()
    losses = []
    for i in range(0, min(len(data) - context - 1, limit * context), context):
        x = torch.from_numpy(data[i : i + context].astype(np.int64))[None].to(device)
        y = torch.from_numpy(data[i + 1 : i + 1 + context].astype(np.int64))[None].to(device)
        with autocast():
            _, loss = model(x, y)
        losses.append(float(loss))
    model.train()
    return float(np.mean(losses)) if losses else float("nan")


@torch.no_grad()
def answer(model, tok, question: str, device: str, max_new: int = 48, context: list[str] | None = None) -> str:
    prompt, _ = sft.format_pair(question, "", context)
    ids = torch.tensor([tok.encode(prompt).ids[-(model.cfg.context - max_new):]], device=device)
    out = model.generate(ids, max_new, temperature=0, stop=tok.token_to_id(sft.END))
    return tok.decode(out[0, ids.size(1):].tolist()).replace(sft.END, "").strip()


def train_loop(model, step_fn, steps: int, peak_lr: float, accumulate: int, device: str, evaluate, label: str):
    opt = optimiser(model, peak_lr)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda" and not torch.cuda.is_bf16_supported())
    best, best_state, curve = float("inf"), None, []
    warmup = max(1, steps // 20)
    for step in range(steps):
        for group in opt.param_groups:
            group["lr"] = schedule(step, steps, peak_lr, warmup)
        for _ in range(accumulate):
            loss = step_fn() / accumulate
            scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)
        if (step + 1) % max(1, steps // 20) == 0 or step + 1 == steps:
            val = evaluate()
            curve.append({"phase": label, "step": step + 1, "train_loss": round(float(loss) * accumulate, 4), "val_loss": round(val, 4)})
            print(f"  [{label}] step {step + 1:>6}  train {float(loss) * accumulate:.3f}  val {val:.3f}")
            if val < best:
                best, best_state = val, {k: v.detach().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return curve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("results/kushmanda"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--steps", type=int, default=4000, help="pretraining optimiser steps")
    parser.add_argument("--sft-steps", type=int, default=3000)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--accumulate", type=int, default=2)
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--layers", type=int, default=6)
    parser.add_argument("--heads", type=int, default=6)
    parser.add_argument("--context", type=int, default=640)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--no-cve", action="store_true", help="leave the NVD descriptions out (v1's corpus)")
    parser.add_argument("--eval-questions", type=int, default=1200)
    parser.add_argument("--tiny", action="store_true")
    args = parser.parse_args()

    started = time.time()
    torch.manual_seed(7)
    random.seed(7)
    rng = np.random.default_rng(7)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
    def autocast():
        return torch.autocast("cuda", dtype=dtype) if device == "cuda" else nullcontext()
    args.out.mkdir(parents=True, exist_ok=True)

    docs = corpus_mod.build(args.cache, args.root, cve=not (args.no_cve or args.tiny))
    train_docs, test_docs = corpus_mod.split(docs)
    by_source: dict[str, int] = {}
    for d in docs:
        by_source[d["source"]] = by_source.get(d["source"], 0) + 1
    sft_train, sft_test = sft.build(args.cache)
    print(f"corpus {len(docs)} docs {by_source}; SFT {len(sft_train)} train / {len(sft_test)} held-out pairs; device {device}")

    tok = train_tokenizer([d["text"] for d in train_docs] + [p["q"] + " " + p["a"] for p in sft_train],
                          512 if args.tiny else 16384)
    tok.save(str(args.out / "tokenizer.json"))
    held_lines = [line for d in test_docs for line in d["text"].splitlines() if line.strip()]

    cfg = (Config(vocab_size=tok.get_vocab_size(), context=256, layers=2, heads=2, width=64)
           if args.tiny else Config(vocab_size=tok.get_vocab_size(), context=args.context, layers=args.layers,
                                    heads=args.heads, width=args.width, dropout=args.dropout))
    model = Kushmanda(cfg).to(device)
    train_ids, test_ids = encode_docs(tok, train_docs), encode_docs(tok, test_docs)
    print(f"model {model.parameters_count() / 1e6:.1f}M parameters; pretraining tokens {len(train_ids):,}")

    steps = 20 if args.tiny else args.steps
    def lm_step():
        x, y = lm_batch(train_ids, cfg.context, args.batch, rng, device)
        with autocast():
            return model(x, y)[1]
    curve = train_loop(model, lm_step, steps, 6e-4, args.accumulate, device,
                       lambda: held_out_loss(model, test_ids, cfg.context, device, autocast), "pretrain")
    pre_loss = held_out_loss(model, test_ids, cfg.context, device, autocast, limit=10_000)

    pad = tok.token_to_id("<|doc|>")
    sft_rows = sft_encode(tok, sft_train, cfg.context)
    sft_test_rows = sft_encode(tok, sft_test, cfg.context)
    def sft_step():
        x, y, m = sft_batch(random.sample(sft_rows, min(args.batch, len(sft_rows))), device, pad)
        with autocast():
            return model(x, y, m)[1]
    @torch.no_grad()
    def sft_val():
        model.eval()
        losses = []
        for i in range(0, min(len(sft_test_rows), 640), args.batch):
            x, y, m = sft_batch(sft_test_rows[i : i + args.batch], device, pad)
            with autocast():
                losses.append(float(model(x, y, m)[1]))
        model.train()
        return float(np.mean(losses))
    curve += train_loop(model, sft_step, 10 if args.tiny else args.sft_steps, 2e-4, 1, device, sft_val, "sft")

    # Grounded answers on held-out entities, scored with the baselines on the same questions.
    questions = random.Random(7).sample(sft_test, min(len(sft_test), 30 if args.tiny else args.eval_questions))
    answers = [answer(model, tok, p["q"], device, 24 if p["kind"] in ("lookup", "classify") else 90, p["context"])
               for p in questions]
    rng_chance = random.Random(7)
    grounded = {
        "kushmanda": evaluate.score(questions, answers),
        "lexical baseline": evaluate.score(questions, [evaluate.lexical(p) for p in questions]),
        "chance": evaluate.score(questions, [evaluate.chance(p, rng_chance) for p in questions]),
    }
    examples, shown = [], set()
    for p, got in zip(questions, answers, strict=True):
        label = p["kind"] if p["answerable"] else "unanswerable"
        if label in shown:
            continue
        shown.add(label)
        examples.append({"kind": label, "question": p["q"][:200], "context": [c[:160] for c in p["context"]],
                         "expected": p["a"][:240], "answer": got[:240]})

    held_bytes = sum(len(d["text"].encode("utf-8")) + 1 for d in test_docs)
    samples = []
    for prompt in PROMPTS:
        ids = torch.tensor([tok.encode(prompt).ids], device=device)
        out = model.generate(ids, 24 if args.tiny else 80, temperature=0.7)
        samples.append({"prompt": prompt, "completion": tok.decode(out[0].tolist()[ids.size(1):])})

    torch.save({"config": cfg.__dict__, "state": model.state_dict()}, args.out / "kushmanda-v2.pt")
    best_step = min((c for c in curve if c["phase"] == "pretrain"), key=lambda c: c["val_loss"])["step"]
    results = {
        "model": "sati-kushmanda-v2",
        "architecture": "decoder-only transformer: RMSNorm, RoPE, SwiGLU, fused causal attention, tied embeddings",
        "parameters": model.parameters_count(),
        "config": cfg.__dict__,
        "device": device,
        "corpus": {"documents": len(docs), "by_source": by_source, "held_out_documents": len(test_docs),
                   "train_tokens": int(len(train_ids)), "held_out_tokens": int(len(test_ids))},
        "tokenizer": {"vocab": tok.get_vocab_size(),
                      "tokens_per_line_held_out": tokens_per_line(lambda s: tok.encode(s).ids, held_lines),
                      "gpt2_tokens_per_line_held_out": gpt2_tokens_per_line(held_lines)},
        "held_out": {"loss": round(pre_loss, 4), "perplexity": round(math.exp(pre_loss), 2),
                     "bits_per_byte": round((pre_loss / math.log(2)) * len(test_ids) / max(1, held_bytes), 4)},
        "sft": {"train_pairs": len(sft_train), "held_out_pairs": len(sft_test),
                "held_out_answer_loss": round(sft_val(), 4), "passages": sft.PASSAGES,
                "unanswerable_share": sft.UNANSWERABLE, "evaluated_questions": len(questions),
                "grounded": grounded, "examples": examples},
        "curve": curve,
        "samples": samples,
        "steps": {"pretrain": steps, "sft": 10 if args.tiny else args.sft_steps},
        # How many times pretraining read the corpus, counting to the kept checkpoint.
        "epochs": round(best_step * args.batch * args.accumulate * cfg.context / max(1, len(train_ids)), 1),
        "seconds": round(time.time() - started, 1),
    }
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"held_out": results["held_out"], "grounded": grounded}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
