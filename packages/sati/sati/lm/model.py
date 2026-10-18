"""Kushmanda — a small GPT-style decoder, written from scratch in PyTorch.

Token and position embeddings, a stack of pre-norm transformer blocks (causal
multi-head self-attention, then an MLP), a final norm, and an output head tied
to the token embedding. Nothing is loaded from a pretrained checkpoint: every
weight is learned from the corpus in `corpus.py`.

Kept deliberately small (about 15M parameters at the default size). It is
narrow — good at security and incident language, not at anything else — and
that is its whole job (RESEARCH PLAN.md, *what "our own model" means*).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class Config:
    vocab_size: int = 8192
    context: int = 256
    layers: int = 6
    heads: int = 6
    width: int = 384
    dropout: float = 0.1


class SelfAttention(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        assert cfg.width % cfg.heads == 0
        self.heads = cfg.heads
        self.qkv = nn.Linear(cfg.width, 3 * cfg.width)
        self.proj = nn.Linear(cfg.width, cfg.width)
        self.drop = nn.Dropout(cfg.dropout)
        mask = torch.tril(torch.ones(cfg.context, cfg.context, dtype=torch.bool))
        self.register_buffer("mask", mask.view(1, 1, cfg.context, cfg.context), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        q, k, v = (z.view(b, t, self.heads, c // self.heads).transpose(1, 2) for z in (q, k, v))
        att = (q @ k.transpose(-2, -1)) / math.sqrt(k.size(-1))
        # The causal mask, applied before the softmax: position t never sees t+1.
        att = att.masked_fill(~self.mask[:, :, :t, :t], float("-inf"))
        att = self.drop(F.softmax(att, dim=-1))
        y = (att @ v).transpose(1, 2).contiguous().view(b, t, c)
        return self.drop(self.proj(y))


class Block(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(cfg.width)
        self.attn = SelfAttention(cfg)
        self.norm2 = nn.LayerNorm(cfg.width)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.width, 4 * cfg.width),
            nn.GELU(),
            nn.Linear(4 * cfg.width, cfg.width),
            nn.Dropout(cfg.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class Kushmanda(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.tokens = nn.Embedding(cfg.vocab_size, cfg.width)
        self.positions = nn.Embedding(cfg.context, cfg.width)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList(Block(cfg) for _ in range(cfg.layers))
        self.norm = nn.LayerNorm(cfg.width)
        self.head = nn.Linear(cfg.width, cfg.vocab_size, bias=False)
        self.head.weight = self.tokens.weight  # tied
        self.apply(self._init)

    @staticmethod
    def _init(module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
        if isinstance(module, nn.Linear) and module.bias is not None:
            nn.init.zeros_(module.bias)

    def parameters_count(self) -> int:
        return sum(p.numel() for p in self.parameters()) - self.positions.weight.numel()

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        _, t = idx.shape
        assert t <= self.cfg.context, "sequence longer than the context"
        pos = torch.arange(t, device=idx.device)
        x = self.drop(self.tokens(idx) + self.positions(pos))
        for block in self.blocks:
            x = block(x)
        logits = self.head(self.norm(x))
        loss = None if targets is None else F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, new_tokens: int, temperature: float = 0.8, top_k: int = 40) -> torch.Tensor:
        self.eval()
        for _ in range(new_tokens):
            window = idx[:, -self.cfg.context :]
            logits, _ = self(window)
            logits = logits[:, -1, :] / max(temperature, 1e-6)
            if top_k:
                kth = torch.topk(logits, min(top_k, logits.size(-1))).values[:, -1, None]
                logits = logits.masked_fill(logits < kth, float("-inf"))
            nxt = torch.multinomial(F.softmax(logits, dim=-1), 1)
            idx = torch.cat([idx, nxt], dim=1)
        return idx
