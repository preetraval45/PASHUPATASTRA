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


TOKENS = 1 << 16
MAX_LEN = 192


def token_ids(text: str, buckets: int = TOKENS) -> list[int]:
    """Hashed words in order; id 0 is padding, so real tokens start at 1."""
    return [1 + zlib.crc32(w.encode()) % (buckets - 1) for w in WORD.findall(text.lower())[:MAX_LEN]] or [1]


class TransformerEncoder(nn.Module):
    """Brahmacharini v1: the same hashed words, but read in order.

    v0 averages a bag of words and bigrams, so "the attacker deleted the
    backups" and "the backups deleted the attacker" are one vector. Here the
    words keep their positions and pass through a small transformer (pre-norm,
    GELU), then a masked mean pool, a projection and L2 normalisation. Trained
    from scratch, with no pretrained weights: Kushmanda's corpus holds the
    procedure examples this model is tested on, so starting from Kushmanda
    would leak the test set.
    """

    def __init__(self, dim: int = 128, width: int = 256, layers: int = 4, heads: int = 4,
                 buckets: int = TOKENS, dropout: float = 0.1) -> None:
        super().__init__()
        self.buckets = buckets
        self.tokens = nn.Embedding(buckets, width, padding_idx=0)
        self.positions = nn.Embedding(MAX_LEN, width)
        block = nn.TransformerEncoderLayer(width, heads, 4 * width, dropout, activation="gelu",
                                           batch_first=True, norm_first=True)
        self.blocks = nn.TransformerEncoder(block, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(width)
        self.proj = nn.Linear(width, dim)
        nn.init.normal_(self.tokens.weight, std=0.02)

    def forward(self, texts: list[str]) -> torch.Tensor:
        device = self.tokens.weight.device
        seqs = [token_ids(t, self.buckets) for t in texts]
        width = max(map(len, seqs))
        ids = torch.zeros(len(seqs), width, dtype=torch.long, device=device)
        for i, s in enumerate(seqs):
            ids[i, : len(s)] = torch.tensor(s, device=device)
        pad = ids == 0
        x = self.tokens(ids) + self.positions(torch.arange(width, device=device))
        x = self.norm(self.blocks(x, src_key_padding_mask=pad))
        keep = (~pad).unsqueeze(-1).float()
        return F.normalize(self.proj((x * keep).sum(1) / keep.sum(1).clamp(min=1)), dim=-1)

    def parameters_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


def info_nce(queries: torch.Tensor, keys: torch.Tensor, temperature: float = 0.05) -> torch.Tensor:
    """Row i's positive is key i; every other key in the batch is a negative."""
    logits = queries @ keys.T / temperature
    return F.cross_entropy(logits, torch.arange(len(queries), device=logits.device))
