# Brand

**Ancient concept → modern intelligence.** The mythology is in the names. It is
not in the artwork.

## The mark

```
        ╭─────────────────────╮
       ╱                       ╲
      │   ⋰                     │
      │  ⋰⋰  ─────✳─────═╪══►   │
      │   ⋰                     │
       ╲                       ╱
        ╰─────────────────────╯
```

Read outward from the centre:

| Element | Meaning |
|---------|---------|
| Circle | The closed loop — Observe → Reason → Act → Verify → Learn |
| Converging lines | Signals arriving: metrics, logs, traces, events |
| Shaft | The arrow in flight, left to right |
| Star node | The decision point, where policy is evaluated |
| Trident head | The astra itself — the action, in gold |

Two colours carry the whole idea: **teal is perception**, **gold is action**.
Nothing is gold until it can act, which is also the product's argument.

Files: [`apps/web/public/mark.svg`](../apps/web/public/mark.svg) (icon),
[`apps/web/public/logo.svg`](../apps/web/public/logo.svg) (horizontal lockup with
tagline). The header component in `apps/web/app/layout.tsx` inlines the same
geometry so it inherits theme colour.

## Relationship to the reference artwork

The mark descends from an illustrated Pashupatastra arrow — trident head, shaft,
star, fletching, teal and gold on cream. The **structure and palette are kept**;
the folk-art execution is not.

This is deliberate. An illustrated weapon reads as a game studio or a personal
project. The same geometry drawn precisely reads as infrastructure — which is
what a buyer is being asked to give production credentials to. The mythology
earns its place by being the *organising idea*, not the decoration.

## Tagline

**Observe. Reason. Act. Verify.**

Four words, four stops, in the order the loop runs. Use it whole. Do not
abbreviate to "Observe. Act." — the two words most often dropped, Reason and
Verify, are the two that distinguish the product from a monitoring tool.

Longer form, for pages with room:

> Autonomous intelligence for complex systems.

## Palette

| Token | Value | Use |
|-------|-------|-----|
| `--ground` | `12 14 18` | Page background |
| `--panel` | `18 21 27` | Surfaces |
| `--edge` | `32 37 46` | Borders, dividers |
| `--ink` | `232 236 241` | Primary text |
| `--muted` | `138 148 163` | Secondary text, labels |
| `--astra` | `47 163 160` | Teal — perception, links, live state |
| `--gold` | `201 162 39` | Gold — action, the trident, decisions |

Risk colours are functional, not decorative, and must stay consistent with the
autonomy tiers: emerald 0–30, amber 31–60, orange 61–80, rose 81+.

## Typography

System sans stack, weight 600 for the wordmark, letter-spacing `0.2em`. Numbers
use tabular figures — a dashboard where digits jitter between refreshes reads as
unreliable, whatever the numbers say.

Monospace for identifiers: incident IDs, action IDs, entity keys, evidence
references. If an operator might paste it into a terminal, it is monospace.

## Rules

**Do:**

- Keep generous clear space around the mark — at least the height of the circle
- Let the mark stand alone as an icon at 16–32px; the wordmark drops away
- Use gold sparingly. If everything is gold, nothing reads as an action

**Do not:**

- Add deities, weapons in the hand, flames, or Sanskrit calligraphy as ornament
- Rotate, skew, or re-colour the mark outside the palette
- Use the mark on a busy photographic background
- Set the wordmark in a blackletter, "fantasy", or faux-Devanagari face
- Translate the tagline into mystical language — it is a technical claim

## Application

The dashboard is the primary brand surface, and it is deliberately quiet: dark
ground, one accent, dense information, no decoration competing with the data. An
operator opens it during an incident. Everything on screen should be either a
fact or a control.
