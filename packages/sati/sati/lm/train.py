"""Train Kushmanda: its own tokenizer, then the model, then the measurements.

    python -m sati.lm.train --out results/kushmanda            # on Kaggle's GPU
    python -m sati.lm.train --out /tmp/k --tiny --steps 20     # smoke test, CPU

Steps, all from this repository's code:

1. Build the corpus (`corpus.py`) and split it **by document** — 5% held out.
2. Train a byte-level BPE tokenizer on the training documents only (RP-41),
   and measure tokens per line on held-out text against GPT-2's tokenizer.
3. Train the decoder (`model.py`) with AdamW, warmup and cosine decay.
4. Report held-out loss, perplexity and **bits per byte** — comparable across
   tokenizers, unlike perplexity — plus sample completions of security prompts.

The weights are Apache-2.0 eligible: every source allows derivative works.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from sati.lm import corpus as corpus_mod
from sati.lm.model import Config, Kushmanda

PROMPTS = (
    "Credential stuffing is",
    "To contain a host that is beaconing to a command-and-control server,",
    "T1566 Phishing",
    "Required action: Apply mitigations",
)


def train_tokenizer(texts: list[str], vocab_size: int):
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

    tok = Tokenizer(models.BPE(unk_token=None))
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=vocab_size, special_tokens=["<|doc|>"],
                                  initial_alphabet=pre_tokenizers.ByteLevel.alphabet())
    tok.train_from_iterator(texts, trainer=trainer)
    return tok


def tokens_per_line(tok, lines: list[str]) -> float:
    return sum(len(tok.encode(line).ids) for line in lines) / max(1, len(lines))


def gpt2_tokens_per_line(lines: list[str]) -> float | None:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("gpt2")
        return sum(len(enc.encode(line)) for line in lines) / max(1, len(lines))
    except Exception:  # noqa: BLE001 — a missing comparison is reported as absent
        return None


def encode_all(tok, docs: list[dict]) -> np.ndarray:
    sep = tok.token_to_id("<|doc|>")
    ids: list[int] = []
    for doc in docs:
        ids.extend(tok.encode(doc["text"]).ids)
        ids.append(sep)
    return np.array(ids, dtype=np.int32)


def batches(data: np.ndarray, context: int, size: int, gen: torch.Generator, device: str):
    starts = torch.randint(0, len(data) - context - 1, (size,), generator=gen)
    x = torch.stack([torch.from_numpy(data[s : s + context].astype(np.int64)) for s in starts.tolist()])
    y = torch.stack([torch.from_numpy(data[s + 1 : s + 1 + context].astype(np.int64)) for s in starts.tolist()])
    return x.to(device), y.to(device)


@torch.no_grad()
def held_out_loss(model: Kushmanda, data: np.ndarray, context: int, device: str, limit: int = 200) -> float:
    model.eval()
    losses = []
    for i in range(0, min(len(data) - context - 1, limit * context), context):
        x = torch.from_numpy(data[i : i + context].astype(np.int64))[None].to(device)
        y = torch.from_numpy(data[i + 1 : i + 1 + context].astype(np.int64))[None].to(device)
        _, loss = model(x, y)
        losses.append(loss.item())
    model.train()
    return float(np.mean(losses)) if losses else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("results/kushmanda"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/corpus"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--steps", type=int, default=6000)
    parser.add_argument("--batch", type=int, default=48)
    parser.add_argument("--vocab", type=int, default=8192)
    parser.add_argument("--tiny", action="store_true", help="a minute-long smoke configuration")
    args = parser.parse_args()

    started = time.time()
    torch.manual_seed(7)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)

    docs = corpus_mod.build(args.cache, args.root)
    train_docs, test_docs = corpus_mod.split(docs)
    by_source: dict[str, int] = {}
    for d in docs:
        by_source[d["source"]] = by_source.get(d["source"], 0) + 1
    print(f"corpus: {len(docs)} documents ({by_source}); held out {len(test_docs)}")

    vocab = 512 if args.tiny else args.vocab
    tok = train_tokenizer([d["text"] for d in train_docs], vocab)
    tok.save(str(args.out / "tokenizer.json"))
    held_lines = [line for d in test_docs for line in d["text"].splitlines() if line.strip()]

    cfg = Config(vocab_size=tok.get_vocab_size(), context=64 if args.tiny else 256,
                 layers=2 if args.tiny else 6, heads=2 if args.tiny else 6,
                 width=64 if args.tiny else 384, dropout=0.1)
    train_ids, test_ids = encode_all(tok, train_docs), encode_all(tok, test_docs)
    model = Kushmanda(cfg).to(device)
    print(f"model: {model.parameters_count() / 1e6:.1f}M parameters on {device}; train tokens {len(train_ids):,}")

    steps = args.steps
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, betas=(0.9, 0.95), weight_decay=0.1)
    warmup = max(1, steps // 20)
    gen = torch.Generator().manual_seed(7)
    curve = []
    for step in range(1, steps + 1):
        lr = 3e-4 * min(1.0, step / warmup) * 0.5 * (1 + math.cos(math.pi * min(1.0, step / steps)))
        for group in opt.param_groups:
            group["lr"] = lr
        x, y = batches(train_ids, cfg.context, args.batch, gen, device)
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % max(1, steps // 20) == 0 or step == steps:
            val = held_out_loss(model, test_ids, cfg.context, device)
            curve.append({"step": step, "train_loss": round(loss.item(), 4), "held_out_loss": round(val, 4)})
            print(f"  step {step:>6}  train {loss.item():.3f}  held-out {val:.3f}")

    final = held_out_loss(model, test_ids, cfg.context, device, limit=10_000)
    held_bytes = sum(len(d["text"].encode("utf-8")) + 1 for d in test_docs)
    bits_per_byte = (final / math.log(2)) * len(test_ids) / max(1, held_bytes)

    samples = []
    for prompt in PROMPTS:
        ids = torch.tensor([tok.encode(prompt).ids], dtype=torch.long, device=device)
        out = model.generate(ids, new_tokens=24 if args.tiny else 80)
        samples.append({"prompt": prompt, "completion": tok.decode(out[0].tolist()[ids.size(1):])})

    torch.save({"config": cfg.__dict__, "state": model.state_dict()}, args.out / "kushmanda-v0.pt")
    results = {
        "model": "sati-kushmanda-v0",
        "parameters": model.parameters_count(),
        "config": cfg.__dict__,
        "device": device,
        "corpus": {"documents": len(docs), "by_source": by_source, "held_out_documents": len(test_docs),
                   "train_tokens": len(train_ids), "held_out_tokens": len(test_ids)},
        "tokenizer": {"vocab": tok.get_vocab_size(),
                      "tokens_per_line_held_out": round(tokens_per_line(tok, held_lines), 2),
                      "gpt2_tokens_per_line_held_out": gpt2_tokens_per_line(held_lines)},
        "held_out": {"loss": round(final, 4), "perplexity": round(math.exp(final), 2),
                     "bits_per_byte": round(bits_per_byte, 4)},
        "curve": curve,
        "samples": samples,
        "steps": steps,
        "seconds": round(time.time() - started, 1),
    }
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["held_out"]), json.dumps(results["tokenizer"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
