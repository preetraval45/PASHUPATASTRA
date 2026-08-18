# Brand

**Ancient concept → modern intelligence.** The mythology is in the names. It is
not in the artwork.

## The mark

The mark is the **Pashupatastra spear**, rendered as illustrated artwork:
crimson flame-head, gold fittings, dark shaft.

File: [`apps/web/public/logo.webp`](../apps/web/public/logo.webp) — 176×176, with
an alpha channel, so it sits on both the dark and light grounds without a plate.
The same file is `apps/web/app/icon.webp`, which Next's file convention serves as
the favicon. The header in `apps/web/app/layout.tsx` renders it as an `<img>`;
unlike the previous geometric mark it does **not** inherit theme colour, because
it carries its own.

### Decision of record — this reverses an earlier one

An earlier version of this document rejected illustrated artwork in favour of a
geometric mark, reasoning that "an illustrated weapon reads as a game studio or a
personal project" while precise geometry "reads as infrastructure — which is what
a buyer is being asked to give production credentials to."

**That decision was reversed by the project owner on 17 August 2026.** The
artwork is now the mark, on every surface. The earlier geometric files
([`mark.svg`](../apps/web/public/mark.svg),
[`logo.svg`](../apps/web/public/logo.svg)) are retained but unused; keep them
until the identity is settled, then delete them rather than leaving two marks in
the repository for someone to pick between.

### Constraints the artwork brings

These are properties of the file, not opinions about it. They govern how it is
used until a purpose-built version exists.

| Constraint | Consequence |
|-----------|-------------|
| The subject is a thin diagonal with wide empty margins | The drawn spear is a fraction of its box. Set it at **32px minimum** in chrome; below roughly 24px it reads as a smudge rather than a mark |
| Source is 176×176 | Adequate for chrome and favicon. **Too small for hero or print** — anything above ~176px will be visibly soft, and upscaling will not fix it |
| Its crimson is close to `--crit` | `--crit` means live execution and critical severity in this interface. Keep the mark out of the status region and never place it beside a severity badge, or the two reds compete for the same meaning |
| It is raster, not vector | It cannot be recoloured, themed, or animated cleanly |

**Owed:** a vector redraw of this artwork at full scale, which removes every row
of that table at once. Until then, treat the current file as the working mark.

### Unresolved: provenance

The artwork's origin and licensing have not been established. This matters more
than a normal asset question, because [ROADMAP.md](ROADMAP.md) Phase 0.10 gates
public launch on trademark clearance, and a logo cannot be registered — or safely
commercialised — without clear rights to it. **Resolve before any public launch,
not after.** See the note in that section.

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
