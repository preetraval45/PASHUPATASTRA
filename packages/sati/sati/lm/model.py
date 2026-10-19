"""Kushmanda — a modern small decoder, written from scratch in PyTorch.

The architecture current small LLMs share, at a size that trains on one GPU:

* **RMSNorm**, pre-norm — cheaper than LayerNorm and as stable.
* **Rotary position embeddings (RoPE)** — positions enter as rotations of the
  query and key vectors, so attention depends on relative distance and there
  is no learned position table.
* **SwiGLU** feed-forward — a gated MLP, consistently better than GELU per
  parameter.
* **Fused causal attention** (`scaled_dot_product_attention`, `is_causal=True`)
  — the causal mask is applied inside the kernel: position t never sees t+1.
* **Tied** input and output embeddings, no biases, and output projections
  initialised scaled by depth so the residual stream starts stable.

Nothing is loaded from a pretrained checkpoint: every weight is learned from the
corpus in `corpus.py`. Narrow by design — security and incident language.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class Config:
    vocab_size: int = 16384
    context: int = 512
    layers: int = 8
    heads: int = 8
    width: int = 512
    dropout: float = 0.0
    rope_base: float = 10000.0


class RMSNorm(nn.Module):
    def __init__(self, width: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(width))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.weight * x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)


def rope_tables(head_dim: int, context: int, base: float) -> tuple[torch.Tensor, torch.Tensor]:
    inv = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
    angles = torch.outer(torch.arange(context).float(), inv)
    return angles.cos(), angles.sin()


def rotate(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    """Rotate pairs of dimensions by their position's angle (RoPE)."""
    x1, x2 = x[..., 0::2], x[..., 1::2]
    out = torch.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), dim=-1)
    return out.flatten(-2)


class Attention(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        assert cfg.width % cfg.heads == 0
        self.heads = cfg.heads
        self.qkv = nn.Linear(cfg.width, 3 * cfg.width, bias=False)
        self.out = nn.Linear(cfg.width, cfg.width, bias=False)
        self.dropout = cfg.dropout

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        q, k, v = self.qkv(x).split(c, dim=2)
        q, k, v = (z.view(b, t, self.heads, c // self.heads).transpose(1, 2) for z in (q, k, v))
        q, k = rotate(q, cos[:t], sin[:t]), rotate(k, cos[:t], sin[:t])
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True, dropout_p=self.dropout if self.training else 0.0)
        return self.out(y.transpose(1, 2).contiguous().view(b, t, c))


class SwiGLU(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        hidden = int(8 * cfg.width / 3 / 64 + 0.999) * 64  # ~2/3 of 4x, rounded to 64
        self.gate = nn.Linear(cfg.width, hidden, bias=False)
        self.up = nn.Linear(cfg.width, hidden, bias=False)
        self.down = nn.Linear(hidden, cfg.width, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down(F.silu(self.gate(x)) * self.up(x))


class Block(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.norm1, self.attn = RMSNorm(cfg.width), Attention(cfg)
        self.norm2, self.mlp = RMSNorm(cfg.width), SwiGLU(cfg)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm1(x), cos, sin)
        return x + self.mlp(self.norm2(x))


class Kushmanda(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.tokens = nn.Embedding(cfg.vocab_size, cfg.width)
        self.blocks = nn.ModuleList(Block(cfg) for _ in range(cfg.layers))
        self.norm = RMSNorm(cfg.width)
        self.head = nn.Linear(cfg.width, cfg.vocab_size, bias=False)
        self.head.weight = self.tokens.weight  # tied
        cos, sin = rope_tables(cfg.width // cfg.heads, cfg.context, cfg.rope_base)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)
        self.apply(self._init)
        for name, p in self.named_parameters():
            if name.endswith(("attn.out.weight", "mlp.down.weight")):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * cfg.layers))

    @staticmethod
    def _init(module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def parameters_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None, mask: torch.Tensor | None = None):
        _, t = idx.shape
        assert t <= self.cfg.context, "sequence longer than the context"
        x = self.tokens(idx)
        for block in self.blocks:
            x = block(x, self.cos, self.sin)
        logits = self.head(self.norm(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.reshape(-1), reduction="none")
        if mask is not None:
            # Supervised fine-tuning: learn the answer, not the question.
            m = mask.reshape(-1).float()
            return logits, (loss * m).sum() / m.sum().clamp(min=1.0)
        return logits, loss.mean()

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, new_tokens: int, temperature: float = 0.7, top_k: int = 40,
                 stop: int | None = None) -> torch.Tensor:
        self.eval()
        for _ in range(new_tokens):
            window = idx[:, -self.cfg.context :]
            logits, _ = self(window)
            logits = logits[:, -1, :]
            if temperature <= 0:
                nxt = logits.argmax(dim=-1, keepdim=True)
            else:
                logits = logits / temperature
                if top_k:
                    kth = torch.topk(logits, min(top_k, logits.size(-1))).values[:, -1, None]
                    logits = logits.masked_fill(logits < kth, float("-inf"))
                nxt = torch.multinomial(F.softmax(logits, dim=-1), 1)
            idx = torch.cat([idx, nxt], dim=1)
            if stop is not None and int(nxt[0, 0]) == stop:
                break
        return idx
