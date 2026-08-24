# Phase 4 closed — Observatory, agent knowledge, blue team

- **Date:** 2026-08-21
- **Phase:** Phase 4 — R29 (final pass)
- **Commit(s):** pending

## State

R24–R29 done. Live and verified against `https://pashupatastra.vercel.app`:
27/27 layout and reachability checks, WCAG AA in both themes, four grounded chat
answers with every citation resolving, three blue team scenarios playable and
discriminating, 916 tests, ruff clean, deployed API and committed OpenAPI spec
agreeing on all 27 routes.

## What the pass found

A pass means trying to break it, not re-running green checks.

- **`openapi.json` was eight routes stale** — the whole chat and game surface.
  Nothing noticed because nothing was looking. `testapi.py` now compares the
  committed paths against the live app, and the test was confirmed to fail on
  the old spec before being trusted on the new one.
- **The not-found page named a console that no longer exists.** It no longer
  lists sections at all — the navigation is already that list and cannot drift
  from itself.
- **A `timeline.tsx` comment still called the audit trail "in-memory and
  per-process today"** — untrue since R18.
- **`verifychat.py` sampled once after `networkidle`** and declared the chat
  panel missing from a page that had one. `networkidle` means the network went
  quiet, not that the page finished rendering.

## Two things stated rather than hidden

- **The console publishes the answers the game uses.** `/incidents/{id}` carries
  chain, confidence and plan, and the scenarios *are* those incidents. Hiding
  them would break the console, which is the product. R27 protects something
  narrower and still worth having: the answer is not in the page you are
  playing on.
- **`notFound()` returns 200, not 404**, because the layout streams before the
  page resolves. The rendered page is right; the status is wrong. Affects
  crawlers rather than readers, and the sitemap lists only real ids.

## The lesson of this whole session

Five times a check was green or red while measuring nothing: the chat verifier
read the visitor's own question back as the reply, then read the previous answer
when a question was rate-limited, then sampled before render; `verifyui` passed
18/18 while the navbar was unnavigable at 768px; the answer cache reported
nothing wrong while missing on every request; the blue team verifier guessed the
answer and graded itself.

**The fix was the same shape every time: assert on what changed between two
runs, not on a value the checker believes it knows.**

## Open, carried forward

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- The Oracle box is unprovisioned, so a model rate limit is a 429 rather than a
  slower answer. `scripts/oracle-ollama.sh` is ready.
- Vercel Hobby is non-commercial — the pricing page in S11, not traffic, is the
  first real bill.

## Next session should

Pick one: **Phase 5** (R50–R55, the visitor's path — a landing page that is not
the console), **Phase 6** (S1–S6, tenancy and identity, whose ordering is not
negotiable), or **Phase A** (R30–R39, the agent that watches a real machine,
which is what the owner originally asked for).
