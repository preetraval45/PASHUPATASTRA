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

## The names

**Owner's reasoning, stated 4 October 2026**, recorded here because a review
that day questioned both names and the answer belongs beside the rules rather
than in a chat log.

| Name | Origin, as the owner chose it | What it maps to |
|------|------------------------------|-----------------|
| **Pashupatastra** | Lord Shiva's most powerful weapon | The platform: the full capability to act on an estate, up to `wipe_host` |
| **Sati** | Mata Sati — the form of the goddess later born as Parvati, Shiva's consort, and Shakti, the power that moves | The agent: the part of the system that acts, reasoning over the engines |

**Why the pair works, and how to say it in one breath.** In the epic, Arjuna
earns the Pashupatastra and never uses it at Kurukshetra — it is held, not
fired. That is this product's design: the system can take drastic actions,
and the architecture exists so that it proposes them and waits. The pairing
holds a second way: in the Shaiva saying, Shiva without Shakti is inert. The
platform's engines are deterministic and have no opinion about what to do
next (CLAUDE.md); Sati is what brings them to bear. Neither reading weakens
rule 2 — Sati proposes, Dharma authorises.

**The known misreading, and what is done about it.** In English and in most
search results, *sati* also names the outlawed practice of widow-burning, and
a first-time reader cannot tell which is meant. The names are kept — that is
the owner's call and this section does not reopen it. The misreading is
handled by context instead:

- The first mention of Sati on any page or document says what it is — *Sati,
  the investigation agent* — so the word is never met bare.
- The capitalised proper noun only; never lower-case *sati* in copy.
- Where there is room for one sentence on origin (an About section, a talk,
  a README), name the goddess explicitly: *named for Mata Sati, Shiva's
  consort*. Naming the source is what removes the ambiguity.
- Whether that origin sentence appears **on the site** is gated by
  [REBUILD.md](REBUILD.md) **R120**, because CLAUDE.md currently keeps the
  mythology to names only and the site copy follows CLAUDE.md.

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
