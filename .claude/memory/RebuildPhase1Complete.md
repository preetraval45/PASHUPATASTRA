# Rebuild Phase 1 complete — the public demo is a blue-team console

- **Date:** 2026-08-20
- **Phase:** Rebuild Phase 1 (docs/REBUILD.md), R1–R8
- **Commit(s):** 5c21972, 61b8337, b67be83, 20d6b6a, 0c2581d, 5865e9e, c6087bd, f274794

## What changed

`pashupatastra.vercel.app` is a security incident-response console. Three
scripted incidents — credential stuffing, phishing to token theft, beaconing
with lateral movement — each with ATT&CK-mapped causal steps, evidence that
resolves to real stored events, and a plan drawn from a 21-action security
registry. No infrastructure action, incident or entity is served to it.

Phase 1 is closed. Phase 2 (look finished) and Phase A (the agent that watches
the owner's machine) are both unstarted.

## Why

The prompt insisted the re-theme is a data-model change rather than a copy
change, and that is right: a security console whose registry says
`restart_service` reads as a theme painted over something else. Every layer was
changed — entity kinds, action registry, incidents, entities on the map,
microcopy — and the infrastructure equivalents are filtered out by domain rather
than deleted, so the executors verified against a live cluster survive.

## Decisions made

- **Domain filtering, not deletion.** `PASHU_ACTION_DOMAIN=security` filters the
  *view*; `get()` still resolves every registered id, so a plan's rollback
  cannot stop resolving because a deployment presents the other domain.
- **R4b: a read-only action can be autonomous when it `changes_nothing`** —
  risk 0 *and* no declared post-state. Before this, all four read-only actions
  needed approval in every environment, so nothing could be diagnosed without a
  human. R19's agent tools depend on this.
- **Undos are not discounted.** `rejoin_network` costs the same as
  `isolate_host`. The infrastructure registry discounts rollbacks because
  restoring a cache is benign; returning a possibly-compromised host to the
  network is not.
- **No invented edges.** The scenarios declare a sequence of events, not a
  dependency graph. Topology shows 11 entities and 0 access paths, which is
  honest — structure inferred from co-occurrence would put fabrication behind
  blast radius, and blast radius feeds risk.
- **Evidence is a link.** An id a reader cannot follow is decoration: it looks
  checkable, so it is taken on trust, and a fabricated reference reads exactly
  like a real one.

## Defects found and fixed along the way

- Citations resolved to nothing (**R6**) — now a route, a page, and a test that
  walks every citation on every incident.
- A missing entity reported **"API unreachable"**, telling visitors the system
  was down when it was fine.
- **React 19 hoists `<title>`**, so the service map's SVG tooltips were emptied
  server-side and the whole map subtree was re-rendered on every load,
  invisibly. Replaced with `aria-label` (**R6b**).
- The map read "no data" beside three open critical incidents — signals sat
  outside the fifteen-minute severity window.
- `MemoryGraph.snapshot` read the wall clock, so a pinned fixture passed for
  fifteen minutes a day.

## Open questions

- The owner asked for `logo.png` as the **Google Search icon**. It is a 3:1
  lockup on a square canvas and is unreadable at 48px; the square spear is the
  legible option and is currently the tab icon. **Raised twice, unanswered.**
- Whether the public demo is worth continuing at all now that Phase A is the
  stated goal. The owner said the site should show real protection of their
  machine, not invented incidents.

## Next session should

- Ask which the owner wants first: Phase 2 (R9–R17, make the demo look
  finished) or Phase A (R30+, the real agent). **Phase A is what they asked
  for; Phase 2 polishes something they called not the point.**
- If Phase A: R30 then **R31 (the privacy allowlist) before any collector
  gathers anything** — an allowlist of permitted fields, never a denylist.
- Real telemetry must never reach the public API. Local-only, `127.0.0.1`.
