"""Brahmacharini v0 — a small dual encoder, written from scratch.

Text becomes hashed word unigrams and bigrams; an `EmbeddingBag` averages their
vectors; a linear layer and L2 normalisation give a 128-dimensional embedding.
The same encoder reads both sides — the observed behaviour and the technique —
so they land in one space, and recall is a cosine nearest-neighbour search.

Trained contrastively (InfoNCE with in-batch negatives): each behaviour is
pulled toward its technique and pushed from the other techniques in the batch.
Small enough to train on a CPU in minutes, which is why it runs on GitHub's
runners rather than a GPU.
"""

from __future__ import annotations

import re
import zlib

import torch
from torch import nn
from torch.nn import functional as F

BUCKETS = 1 << 18
WORD = re.compile(r"[a-z0-9][a-z0-9\-\.]*")


def hashed(text: str, buckets: int = BUCKETS) -> list[int]:
    words = WORD.findall(text.lower())
    grams = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
    return [zlib.crc32(g.encode()) % buckets for g in grams] or [0]


class Encoder(nn.Module):
    def __init__(self, dim: int = 128, width: int = 256, buckets: int = BUCKETS) -> None:
        super().__init__()
        self.buckets = buckets
        self.bag = nn.EmbeddingBag(buckets, width, mode="mean")
        self.proj = nn.Linear(width, dim)
        nn.init.normal_(self.bag.weight, std=0.05)

    def forward(self, texts: list[str]) -> torch.Tensor:
        ids, offsets = [], []
        for text in texts:
            offsets.append(len(ids))
            ids.extend(hashed(text, self.buckets))
        flat = torch.tensor(ids, dtype=torch.long)
        starts = torch.tensor(offsets, dtype=torch.long)
        return F.normalize(self.proj(self.bag(flat, starts)), dim=-1)


def info_nce(queries: torch.Tensor, keys: torch.Tensor, temperature: float = 0.05) -> torch.Tensor:
    """Row i's positive is key i; every other key in the batch is a negative."""
    logits = queries @ keys.T / temperature
    return F.cross_entropy(logits, torch.arange(len(queries)))
