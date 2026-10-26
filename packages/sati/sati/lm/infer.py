"""Kushmanda inference in numpy: no PyTorch, so it can be served from a Lambda zip (RP-44/45).

The model (`sati.lm.model.Kushmanda`) is 16.9M parameters. PyTorch alone is
far larger than a Lambda deployment allows, and numpy is not. This module runs
the same forward pass with a key/value cache, so each new token costs one
pass over the model's matrices (a few milliseconds), not one over the whole
sequence.

Weights come from `export()`: every matrix stored int8 with one scale per
output row (about 17 MB instead of 68 MB), and the vectors (norm weights) in
float32. `tests/testlminfer.py` checks that the numpy forward pass matches
PyTorch's logits on a random model, unquantised exactly and quantised
closely.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _rms(x: np.ndarray, w: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return w * x / np.sqrt((x * x).mean(-1, keepdims=True) + eps)


def _silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-x))


def _rope_tables(head_dim: int, context: int, base: float) -> tuple[np.ndarray, np.ndarray]:
    inv = 1.0 / (base ** (np.arange(0, head_dim, 2, dtype=np.float64) / head_dim))
    angles = np.outer(np.arange(context, dtype=np.float64), inv)
    return np.cos(angles).astype(np.float32), np.sin(angles).astype(np.float32)


def _rotate(x: np.ndarray, cos: np.ndarray, sin: np.ndarray) -> np.ndarray:
    """RoPE on interleaved pairs, as `sati.lm.model.rotate`. x: (..., t, d)."""
    x1, x2 = x[..., 0::2], x[..., 1::2]
    out = np.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), axis=-1)
    return out.reshape(x.shape)


class Engine:
    """Greedy (or temperature) decoding over exported Kushmanda weights."""

    def __init__(self, config: dict, weights: dict[str, np.ndarray]) -> None:
        self.cfg = config
        self.w = weights
        self.heads = int(config["heads"])
        self.width = int(config["width"])
        self.cos, self.sin = _rope_tables(self.width // self.heads, int(config["context"]), float(config["rope_base"]))

    # -- loading ---------------------------------------------------------------

    @classmethod
    def load(cls, folder: Path) -> Engine:
        meta = json.loads((folder / "kushmanda.json").read_text(encoding="utf-8"))
        packed = np.load(folder / "kushmanda.npz")
        weights = {}
        for name in meta["tensors"]:
            if f"{name}.q" in packed:
                weights[name] = packed[f"{name}.q"].astype(np.float32) * packed[f"{name}.s"][:, None]
            else:
                weights[name] = packed[name].astype(np.float32)
        return cls(meta["config"], weights)

    # -- the forward pass ------------------------------------------------------

    def _layer(self, i: int, x: np.ndarray, start: int, cache: list) -> np.ndarray:
        w, h = self.w, self.heads
        t, c = x.shape
        d = c // h
        a = _rms(x, w[f"blocks.{i}.norm1.weight"])
        qkv = a @ w[f"blocks.{i}.attn.qkv.weight"].T
        q, k, v = (z.reshape(t, h, d).transpose(1, 0, 2) for z in np.split(qkv, 3, axis=-1))
        cos, sin = self.cos[start : start + t], self.sin[start : start + t]
        q, k = _rotate(q, cos, sin), _rotate(k, cos, sin)
        if cache[i] is not None:
            k = np.concatenate([cache[i][0], k], axis=1)
            v = np.concatenate([cache[i][1], v], axis=1)
        cache[i] = (k, v)
        scores = q @ k.transpose(0, 2, 1) / np.sqrt(d)
        total = k.shape[1]
        # Causal: query at absolute position start+j sees keys 0..start+j.
        mask = np.arange(total)[None, :] > (start + np.arange(t))[:, None]
        scores = np.where(mask[None], -np.inf, scores)
        scores = np.exp(scores - scores.max(-1, keepdims=True))
        att = (scores / scores.sum(-1, keepdims=True)) @ v
        x = x + att.transpose(1, 0, 2).reshape(t, c) @ w[f"blocks.{i}.attn.out.weight"].T
        m = _rms(x, w[f"blocks.{i}.norm2.weight"])
        hidden = _silu(m @ w[f"blocks.{i}.mlp.gate.weight"].T) * (m @ w[f"blocks.{i}.mlp.up.weight"].T)
        return x + hidden @ w[f"blocks.{i}.mlp.down.weight"].T

    def logits(self, ids: list[int], start: int = 0, cache: list | None = None) -> np.ndarray:
        """Logits for every position of `ids`, continuing from `cache` if given."""
        cache = cache if cache is not None else [None] * int(self.cfg["layers"])
        x = self.w["tokens.weight"][np.asarray(ids)]
        for i in range(int(self.cfg["layers"])):
            x = self._layer(i, x, start, cache)
        return _rms(x, self.w["norm.weight"]) @ self.w["tokens.weight"].T  # tied head

    def generate(self, ids: list[int], new_tokens: int, stop: int | None = None) -> list[int]:
        """Greedy continuation, one cached step per token."""
        ctx = int(self.cfg["context"])
        ids = list(ids)[-(ctx - new_tokens):]
        cache: list = [None] * int(self.cfg["layers"])
        out = self.logits(ids, 0, cache)
        produced: list[int] = []
        for _ in range(new_tokens):
            nxt = int(out[-1].argmax())
            if stop is not None and nxt == stop:
                break
            produced.append(nxt)
            out = self.logits([nxt], len(ids) + len(produced) - 1, cache)
        return produced


def export(state: dict[str, "object"], config: dict, folder: Path, quantise: bool = True) -> None:
    """Write `kushmanda.npz` and `kushmanda.json` from a PyTorch state dict
    (tensors already on CPU). Matrices become int8 with a scale per row."""
    folder.mkdir(parents=True, exist_ok=True)
    arrays, names = {}, []
    for name, tensor in state.items():
        if name == "head.weight":
            continue  # tied to tokens.weight
        a = np.asarray(tensor.float().numpy() if hasattr(tensor, "float") else tensor, dtype=np.float32)
        names.append(name)
        if quantise and a.ndim == 2:
            scale = np.maximum(np.abs(a).max(axis=1), 1e-12) / 127.0
            arrays[f"{name}.q"] = np.round(a / scale[:, None]).astype(np.int8)
            arrays[f"{name}.s"] = scale.astype(np.float32)
        else:
            arrays[name] = a
    np.savez_compressed(folder / "kushmanda.npz", **arrays)
    (folder / "kushmanda.json").write_text(json.dumps({"config": config, "tensors": names, "quantised": quantise}),
                                          encoding="utf-8")
