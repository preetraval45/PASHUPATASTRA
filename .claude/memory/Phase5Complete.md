# Phase 5 closed — the visitor's path

- **Date:** 2026-08-24
- **Phase:** Phase 5 — R55 (final pass)
- **Commit(s):** pending

## State

R50–R55 done. `/` is a landing page, the console is at `/overview`, the map is
beside the incident it belongs to, and the navigation follows the visitor rather
than the architecture. 33/33 layout checks, WCAG AA both themes, 939 tests, all
five verifiers green.

## What the phase actually fixed

A stranger used to land in an operator's console. They now land on a claim —
*four alerts in four tools are one intrusion* — and reach a real incident in one
click, with everything above the fold at 375px.

## Decisions worth keeping

- **No edge without a citation** (R50). The seed added none at all, which was
  right about the danger and wrong about the remedy: the map was disconnected
  boxes and `isolate_host` priced its risk against an estate of one.
- **Edge direction runs asset → account**, because `blast_radius` walks
  dependents. Reversed, compromising a mailbox would endanger the attacker and
  every risk score would be backwards while still looking like a number.
- **The nav rule beat the nav number** (R52). The task said "three items",
  written when there were five; phases 3–4 added three sections that each pass
  *would a stranger go looking for this?* Applying the number would have deleted
  three sections for arithmetic.
- **The risk table is generated from the engine** (R54), proved by moving a tier
  boundary and watching the page follow. A table typed into a page is a second
  answer to "who may approve this".
- **No invented numbers on the front page.** MTTR is not computable here, so the
  arithmetic is made of the demo's own checkable figures — signals arriving 11,
  30 and 90 minutes apart.

## What the reviews caught

Each phase-closing pass found something no green check would have:

- the not-found page naming a console that no longer existed, twice — once for
  its section list (R29) and once for its button label (R55)
- the audit trail unreachable from an incident, while the justification for
  delisting it said otherwise (R52)
- every overview incident card linking to the list rather than the incident
- the landing page's "open it" link pointing at a different incident from the
  one the panel described
- two unsubstantiated claims, found by walking `/` and looking for backing
- a 56-character URLhaus subdomain overflowing `/observatory` at 375px

## The recurring lesson, now seven times

A check can be green while measuring nothing. The chat verifier read the
question back as the reply, then read the previous answer, then sampled before
render; `verifyui` passed while the navbar was unnavigable; the answer cache
reported healthy while missing every request; the blue team verifier graded
itself; `verifyreach` satisfied "from an incident" using the overview's link.

**The fix was identical every time: assert on what changed between two runs, not
on a value the checker believes it knows.**

## Carried forward

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- `estimated_users` is 0 everywhere: blast radius reports real entity counts and
  an absent user figure. Absent rather than wrong.
- `notFound()` returns 200, not 404 — the layout streams before the page
  resolves. Readers see the right page; crawlers see the wrong status.
- Vercel Hobby is non-commercial. S11's pricing page is the first real bill.
- The Oracle box is unprovisioned, so a model rate limit is a 429.

## Next session should

Pick one: **Phase 6** (S1–S6, tenancy and identity — the SaaS floor, whose
ordering is not negotiable), or **Phase A** (R30–R39, the agent that watches a
real machine, which is what the owner originally asked for).
