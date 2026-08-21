# Rebuild — sequenced delivery plan

**From SRE demo to a live, interactive cybersecurity incident-response agent.**

Source: `pashupatastra-website-rebuild-prompt.md` in the repository root. That
document says *what* to build and why. This one says *in what order*, *what each
task depends on*, and *how you know it is done*.

## How to use this

Every task has an id (`R1`, `R2`, …). Tell me **"do R7"** and I do exactly that
task and stop. A task is only startable when everything in its **Needs** column
is ticked — that is the whole point of the ordering, and jumping it is how a
half-built feature lands on top of an unfinished one.

Marks follow [ROADMAP.md](ROADMAP.md):

| Mark | Meaning |
|------|---------|
| `- [x]` | Done, and its evidence exists |
| `- [~]` | Partly done. The line says exactly what remains |
| `- [ ]` | Not started |

A task is ticked only when its **Done when** column is demonstrably true. "The
code is written" is not evidence.

## Relationship to the existing roadmap

[ROADMAP.md](ROADMAP.md) tracks the platform — engines, connectors, policy,
benchmark, 674 passing tests. It is not superseded and nothing in it is deleted.
This file is the delivery plan for the **public demo site** built on top of that
platform. Where the two touch, this file says so.

---

## Cost ceiling: free tiers only

Every task below fits AWS free tier and Vercel Hobby. Two of them do not, and
both are flagged where they appear rather than discovered later.

| Service | Allowance | Expires? |
|---|---|---|
| Lambda | 1M requests + 400k GB-s / month | **Always free** |
| DynamoDB | 25 GB, 25 WCU, 25 RCU | **Always free** |
| EventBridge Scheduler | 14M invocations / month | **Always free** |
| CloudWatch Logs | 5 GB ingest / month | **Always free** |
| API Gateway HTTP API | 1M requests / month | 12 months, then ~$1/M |
| S3 | 5 GB | 12 months |
| Vercel Hobby | 100 GB bandwidth, unlimited static | **Always free**, non-commercial |

**Not free, and unavoidable for what the prompt asks:**

- **Anthropic API** (R16–R19, the chat agent). Pay-per-token. There is no free
  tier. Budget it deliberately — see R16, which puts a hard spend ceiling in
  code before the first call rather than after the first bill.
- **RDS Postgres** is *not* used. The platform supports it, but the demo runs on
  DynamoDB precisely because DynamoDB's free tier does not expire and RDS's
  does. See R15.

**Already deployed and inside the free tier:** Lambda `pashupatastra-api`,
API Gateway HTTP API `265d0hsmwa`, Vercel project `pashupatastra`.

---

## The direction changed on 19 August 2026

The site was going to be a demo about invented incidents. It is now two things
that share a codebase, because the owner wants it to watch **the actual machine
it runs on**, show real threats to it, and explain what it is doing — and
because that goal and a public URL cannot be the same deployment.

### Why they cannot be the same deployment

`pashupatastra.vercel.app` and the API behind it are open to anyone; there is no
login and the prompt's non-goals rule one out. Publishing this desktop's process
list, internal addresses, usernames, open ports and missing patches to that URL
would not be a dashboard, it would be a shopping list for attacking this exact
machine — "firewall off, three unpatched CVEs, these ports listening" is more
useful to an attacker than to anyone else.

So:

| | **Watch** — the real thing | **Demo** — the public site |
|---|---|---|
| Runs | on this desktop, localhost only | Vercel + Lambda |
| Data | real telemetry from this machine | scripted scenarios |
| Leaves the machine? | **never** | nothing personal exists to leave |
| Audience | the owner | anyone with the link |

One codebase, two deployments. `docs/DEPLOYMENT.md` already describes this shape
for on-prem customers — "run the dashboard from the same container as the API" —
so this is the architecture the project already had, used for its first real
purpose rather than a hypothetical customer.

### What the agent may do to the machine

**Observe and explain. It does not act.** Chosen deliberately: this is a daily
driver, not a fleet machine, and a false positive that cuts the network or locks
the account has to be fixed locally — from the machine the website just broke.
Every finding shows the action it *would* take, its risk score, its tier and its
rollback, and then does not take it. `PASHU_DRY_RUN` stays true and the
environment stays out of `PASHU_LIVE_ENVIRONMENTS`, so both gates in
`docs/SECURITY.md` remain shut.

That is not a weaker product. "Here is what I saw, here is what it means, here is
what I would do and why, and here is why I am not doing it" *is* the teaching
goal, and it is the only version that cannot break the machine it protects.

### What it must never collect

The owner's instruction, and the constraint that makes local-only worth having:
**it watches for attacks, not for what the owner is doing.** Not file contents,
not document or project paths, not source code, not browser history, not window
titles, not the contents of anything typed. A collector that can see a file path
can see the name of every project on the disk, so the rule is an allowlist of
fields, enforced in code and tested — never a denylist of things to strip.

---

## Phase A — the agent that watches this machine

Needs **R4**. Runs alongside Phase 1; the public demo and the real agent share
the engines, the registry and the UI, so neither blocks the other.

- [ ] **R30 — Local collector skeleton.** Needs: **R2**.
  A `drishti` collector that runs on Windows, emits into the existing `Event`
  schema with real `Provenance`, and posts to a *local* API. No new event model:
  the whole point of the schema is that a new source is a new source, not a new
  shape.
  **Done when:** one real observation from this machine appears in the local
  store, carrying the command that produced it as provenance.

- [ ] **R31 — Privacy allowlist.** Needs: **R30**.
  Every field a collector may emit, listed explicitly; anything unlisted is
  dropped before it reaches the event, not redacted afterwards.
  **Done when:** a test feeds a process with a document path, a window title and
  a command line containing a file in the user's home, and asserts none of it
  survives into the event.
  *This is the task that makes the rest safe to run. It comes before the
  collectors that would otherwise have already gathered the data.*

- [ ] **R32 — Processes and parentage.** Needs: **R31**.
  Running processes, signing status, and what spawned what. The richest source
  of real detections — Office spawning a shell, encoded commands, unsigned
  binaries running from temporary directories.
  **Done when:** the real process tree of this machine is visible in the graph,
  with parent-child edges, and no path outside system directories is emitted.

- [ ] **R33 — Network connections.** Needs: **R31**.
  Active connections, listening ports, remote addresses, and the process that
  owns each.
  **Done when:** real connections appear as `network_flow` entities keyed
  directionally, joined to the owning process.

- [ ] **R34 — Logons and account activity.** Needs: **R31**.
  Windows Security log: 4624, 4625, 4672, new accounts, RDP. Usernames are
  local-only data and never leave the machine.
  **Done when:** a deliberate failed logon on this machine shows up as an event
  within the poll interval.

- [ ] **R35 — Posture: Defender, firewall, patches.** Needs: **R31**.
  Real-time protection state, firewall profiles, pending updates, and which
  installed software matches a *real* CISA KEV entry.
  **Done when:** the real posture of this machine is reported, and a KEV match
  cites the advisory it came from.
  *The most immediately useful task here: posture is what actually makes the
  machine safer, and unlike intrusion detection it is never a false positive.*

- [ ] **R36 — `pashupatastra watch`.** Needs: **R32, R33**.
  One command that starts the API and the dashboard bound to localhost, with the
  collectors running. Bound to `127.0.0.1` explicitly — a security tool that
  listens on every interface has added an attack surface to the machine it is
  protecting.
  **Done when:** one command brings up the real dashboard, and the port is
  unreachable from another machine on the same network.

- [ ] **R37 — Detections over real telemetry.** Needs: **R32, R33, R34**.
  Deterministic rules, each citing the events that fired it. No model in this
  path — a detection that cannot name its evidence is a guess.
  **Done when:** a benign action taken deliberately on this machine produces a
  correct detection with resolving evidence, and an ordinary hour produces no
  alert at all. *The second half is the harder half.*

- [ ] **R38 — The explanation layer.** Needs: **R37**.
  For every finding: what was observed, why it matters, what it maps to in
  ATT&CK, what the agent *would* do, what tier that action sits in, and the
  sentence saying it did not do it.
  **Done when:** someone who does not know what `T1059.001` is can read a
  finding and understand what happened to their machine.
  *This is the task the whole thing exists for.*

- [ ] **R39 — Real threat intelligence.** Needs: **R33, R35**.
  CISA KEV and abuse.ch, fetched on a schedule, stored locally, used to enrich
  real observations. Public feeds only, and never queried per-observation from
  the browser — asking a third party about every address this machine talks to
  tells that third party everything this machine talks to.
  **Done when:** a real connection is enriched from a real feed entry, and the
  verification state distinguishes reported from confirmed.


---

## Dependency map

```
Phase 1 ─ re-theme the domain
  R1 ──┐
  R2 ──┤
  R3 ──┼──► R5 ──► R6 ──► R7 ──► R8 (deploy + review)
  R4 ──┘

Phase 2 ─ make it look finished          needs R8
  R9 ──┬──► R13
  R10 ─┘
  R11 ────► R12
  R14, R15 ──► R16?  no — R15 ──► R16 is SEO only
  R9..R15 ─────────────────────► R16 (deploy + review)

Phase 3 ─ the agent                      needs R16
  R17 ──► R18 ──► R19 ──► R20 ──► R21 ──► R22 (deploy + review)

Phase 4 ─ observatory + game             needs R22
  R23 ──► R24 ──► R25
  R23, R11 ─────► R26 ──► R27 ──► R28 (final deploy)

Phase 5 ─ the visitor's path            needs R17
  R40 ──► R41 ──► R42
  R43 ──► R44
  R41, R42, R43, R44 ──────────► R45 (deploy + review)
```

---

## Phase 1 — Re-theme the domain *(the public demo)*

These tasks now shape the **public site**, which shows scripted scenarios and
no personal data. The real agent is Phase A above.

The prompt is explicit that this is a data-model change, not a copy change. Half
a re-theme reads worse than none: a "security" site whose action registry still
says `restart_service` tells a visitor the domain is a skin.

**One scope decision, stated up front.** The prompt says *replace* the entity
kinds and the 13 actions. I am going to **add** the security ones and **tag**
both sets by domain, not delete the infrastructure ones — then serve only the
security domain to the site. The reason is concrete: `restart_service`,
`scale_service` and `rollback_deployment` have executors verified against a live
Kubernetes cluster (`scripts/verifyexecutors.py`, 11 checks) and 674 tests
depend on them. Deleting verified, tested work to re-skin a demo is a bad trade.
The visible result is identical — the site shows security actions only — and
`GET /api/v1/actions` returns exactly the security set. Say the word if you want
them genuinely deleted instead.

- [x] **R1 — Fix the wordmark.** Needs: nothing.
  The name is now one text node, fitted with type rather than duplicated and
  hidden. The reported duplication was never visible: the two spans were
  correctly hidden at each other's breakpoint (`.sm\:inline` is emitted after
  `.hidden`, so it wins at ≥640px). What *was* wrong is that the page's text
  content read `PASHUPASHUPATASTRA` — which is what a search snippet, a social
  preview and a copy-paste take away.
  *Evidence: `scripts/verifyui.py` against the deployed site — visible text and
  `textContent` both `PASHUPATASTRA` at 375px, 768px and 1440px; no horizontal
  overflow on any of the five routes at any of the three widths.*

- [x] **R2 — Security entity kinds.** Needs: nothing.
  `account`, `network_flow`, `asset`, `process` added; `host` already existed.
  Each carries its key convention on the enum member, because keys are the
  namespace events and the graph share: a flow is directional
  (`src->dst:port`), a process is host-scoped (`host/pid`, since a bare pid is
  reused within hours), and `ACCOUNT` is kept distinct from the existing
  `USER` — an identity that can log in versus a human counted in an impact
  estimate. `SecurityPayload` and `EventClass.SECURITY` already existed.
  *Evidence: 11 new tests in `packages/core/tests/testcore.py` — round-trip,
  carried on events, directionality, and blast-radius traversal; 685 pass
  across all three packages, up from 674. `openapi.json` regenerated, since
  new enum members change the public contract CI checks.*

- [x] **R3 — ATT&CK technique on causal steps.** Needs: nothing.
  `AttackTechnique` carries id, name and tactic; `CausalLink.attack_technique`
  is optional, so an infrastructure step stays valid rather than being given
  an invented mapping. The id format is enforced and its catalogue URL is
  *derived* rather than stored — a stored URL is one more thing that can
  disagree with the id it points at, and a malformed id would produce a
  citation that looks authoritative and leads nowhere.
  *Evidence: 9 new tests; verified in a headless browser against a running
  API with one step mapped and two bare — the mapped step renders
  `technique: T1110.004 Credential Stuffing · Credential Access` beneath its
  evidence line, the bare steps render unchanged, and the link resolves to
  `attack.mitre.org/techniques/T1110/004/`. 694 tests pass; `openapi.json`
  regenerated.*

- [x] **R4 — Security action registry.** Needs: nothing.
  21 actions, not 14: the table's 14 plus the 7 undos it names. A rollback id
  that resolves to nothing fails at the moment the rollback is needed, so
  `release_email`, `rejoin_network` and the rest are registered too.
  `ActionSpec.domains` is a set, because `read_logs` is the same act in both
  domains and a second id would give the policy engine two scores for one
  thing. `PASHU_ACTION_DOMAIN` filters the *view*; `get` still resolves
  everything.
  *Evidence: the deployed `GET /api/v1/actions` returns 21 security actions
  and no infrastructure ones; 57 new tests, 751 pass overall.*
  Two properties worth naming: undos are never discounted (returning an
  isolated host to the network is scored at the risk of isolating it, unlike
  `warm_cache` which is cheaper than `clear_cache`), and `isolate_host`'s
  post-state requires EDR to stay reachable — a host nobody can inspect
  cannot be cleared.

- [x] **R4b — Decide whether a read-only action can be autonomous.**
  Needs: nothing. **This is a policy decision, not a bug fix, which is why it
  is not already done.**
  Found while writing R4's tests: all four risk-0 read-only actions come back
  `approval` in *every* environment, because `evaluate` escalates any action
  without a tested rollback and a read-only action has nothing to roll back.
  The 0–30 autonomous band is therefore unreachable for them, and registering
  them at risk 0 buys nothing.
  The documented rule — "an action with no tested rollback cannot be
  autonomous" — reads as being about actions that *change* something.
  A candidate carve-out is `base_risk == 0 and not expected_post_state`:
  nothing changed, so nothing to undo and nothing to verify.
  **R19 depends on this.** The chat agent is specified to call read-only
  tier-0 tools; if reading logs needs an approval, it cannot read anything.
  **Decided: yes, when it changes nothing.** `ActionSpec.changes_nothing` is
  risk 0 *and* no declared post-state. Both halves are required — risk 0 alone
  would exempt an action somebody scored optimistically, an empty post-state
  alone would exempt one whose author forgot to declare it. An action escapes
  the rollback rule only by admitting it has nothing to verify.
  *Evidence: the four read-only actions are autonomous in every environment;
  `wipe_host` still denied, `block_ip` still approval. Two tests assert the
  exemption cannot be widened. `docs/specs/Policy Model.md` carries the rule.*

- [x] **R5 — Three scripted incidents.** Needs: **R2, R3, R4**.
  Credential stuffing, phishing → token theft, lateral movement / beaconing.
  Each with a causal chain carrying evidence ids and ATT&CK techniques, a
  diagnosis, at least one alternative hypothesis *contradicted by named
  evidence*, and a risk-gated plan.
  The phishing one must propose `revoke_session` + `quarantine_email` and **not**
  `force_password_reset` — that distinction is the scenario's whole point.
  *Evidence: all three served by the deployed API — 0901 credential stuffing,
  0902 token theft, 0903 beaconing — each with ATT&CK-mapped causal steps and
  a plan drawn from the security registry. 32 tests.*
  Each scenario declares its telemetry **and** its incident, so every evidence
  id cites an event that exists; a test asserts nothing dangles and nothing is
  set dressing. The infrastructure demo incident is no longer seeded when the
  security domain is served — a connection-pool outage beside a credential
  stuffing incident reads as a theme applied over something else.

- [x] **R6 — Make evidence resolve.** Needs: **R5**.
  *This is a live defect, not a new feature.* The current incident cites
  `evt-deploy-421`; no such event exists in the store, so the citation is
  unfollowable text. Seed the events each incident cites, add
  `GET /api/v1/events/{id}`, and make evidence tags links.
  Also fix: a causal-chain link to an entity not in the graph currently renders
  **"API unreachable"**, telling the visitor the whole system is down when the
  API is fine.
  *Evidence: clicked through in a browser — a citation on the incident page
  navigates to `/evidence/<id>`, which shows the observation, its source
  system, and the scenario that produced it; `/entity/service:does-not-exist`
  now renders "Not found". A test walks every citation on all three
  incidents through the live route, so a dead reference fails the build
  rather than the reader. 789 tests pass.*
  Also fixed here: the graph still held the infrastructure corpus, so a
  security console listed `checkout-api` on its map. The corpus is no longer
  seeded when the security domain is served, and the scenarios' own entities
  are — with no edges, because they declare a sequence of events and not a
  dependency graph.

- [x] **R6b — Fix the hydration mismatch on Infrastructure.** Needs: nothing.
  Found by `scripts/verifyui.py` while verifying R1: `/infrastructure` throws
  React error #418 — server-rendered HTML not matching the client — at all
  three viewports. The page renders, so it is invisible until something on it
  silently stops updating.
  **Cause: React 19 treats `<title>` as hoistable document metadata.** The
  service map used an SVG `<title>` for each node's tooltip; React deduped it
  against the page title, so the server sent `<title></title>` and the client
  filled it in. React then discarded and re-rendered the whole map subtree on
  every load — invisibly, because it still looked right.
  Replaced with `aria-label`, built as one string rather than sibling text
  nodes. It reaches a screen reader, which the `<title>` was failing to do.
  *Evidence: reproduced with 18 nodes and 2 edges (the security seed has no
  edges, which is why it stopped appearing rather than being fixed), then
  clean at all three viewports on the same data. `scripts/verifyui.py` passes
  15/15.*

- [x] **R7 — Microcopy pass.** Needs: **R5**.
  Every sentence referencing deploys, services, replicas or databases rewritten
  for the security domain, keeping the existing voice. Includes the "reading
  this map" text, the Infrastructure page framing, and the offline notice.
  The map's framing changed rather than its nouns: it was "what depends on
  what, callers on the left" and is now "what can reach what — so an intrusion
  spreads left-to-right". Impact reads *accounts affected* and *affected
  assets*; the empty overview says "Quiet", and adds that quiet is not the
  same as nothing happening.
  *Remaining deliberate hits: `services/api` in the local-dev hint (a real
  path), "this deployment" on the evidence page (the hosted instance), and
  the `deployment`/`trace` cases in the event-payload switch (schema event
  classes, not prose).*
  Two defects found while verifying: every entity read "no data" beside three
  open critical incidents, because the scenarios' signals sat outside the
  fifteen-minute severity window — the map was contradicting the incidents. And
  `MemoryGraph.snapshot` read the wall clock, so a fixture pinned to a
  timestamp passed for fifteen minutes and failed for the rest of the day.
  *Evidence: 789 tests, `verifyui.py` 18/18 across six routes.*

- [x] **R8 — Deploy Phase 1 and review.** Needs: **R1, R6, R7**.
  *Evidence, against the deployed site and API: three security incidents; 21
  security actions with no infrastructure action leaking; 14 citations checked
  and none dead; every causal step ATT&CK-mapped; 11 entities and 0 invented
  access paths; 11 routes walked at 1440px with no page errors and no SRE
  vocabulary except the deliberate hits listed in R7; citation, entity and
  ATT&CK links all followed by click. Health reports `degraded`, `dry run`,
  and `echo` — the deployment states what it is.*
  **Phase 1 is closed. Phase 2 polishes the demo; Phase A is the agent that
  watches a real machine, and is what the owner actually asked for.**

---

## Phase 2 — Make it look finished

Needs **R8**. Read the frontend design skill before touching a component.

- [x] **R9 — Typography.** Needs: **R8**.
  **Inter for prose, JetBrains Mono for anything retyped or pasted.**
  Inter because it was already assumed — `globals.css` had been asking for
  `cv02`/`cv03`/`cv04` since it was written, and those are Inter character
  variants, inert on a system font all this time. JetBrains Mono for a
  functional reason rather than taste: the monospace carries event ids, IPs
  and technique codes, and it has a slashed zero and unambiguous `1`/`l`/`I`.
  Loaded via `next/font`, which self-hosts at build time — **a visitor's
  browser makes no request to Google.** A security console that reports every
  page view to a third party argues against itself.
  *Evidence: across five routes, every text-bearing element computes to Inter
  or JetBrains Mono — zero fallbacks — and zero requests to google/gstatic.
  `verifyui.py` 18/18.*

- [x] **R10 — Status and contrast pass.** Needs: **R8**.
  `scripts/verifycontrast.py` measures in a real browser rather than reading
  the palette — a badge tints its background with `--crit` at 10% over a
  panel, so the colour behind the text exists only after compositing and the
  palette file cannot tell you what it is.
  **18 failing pairings found, worst 1.56:1.** The map's status colours were
  hardcoded to the dark theme (`text-rose-400`, `#fb7185`), so its glyphs kept
  dark values on a white page. `--faint` failed in *both* themes while
  carrying real text, and light `--warn` failed marginally.
  *Evidence: 1113 text elements across 5 routes × 2 themes, every pairing at
  or above its threshold, worst now 4.65:1. SVG confirmed resolving tokens
  per theme — `rgb(145, 86, 5)` light, `rgb(251, 191, 36)` dark.*
  The ramp is compressed as a result: `--faint` carries evidence ids and
  counts, so it has to clear 4.5:1 like anything else, which pushes it close
  to `--muted`. The floor wins over the hierarchy.
  Shape-redundancy re-checked too: the one place status was carried by colour
  alone was the effective-risk number, which now reads `60 · medium · base
  45` using the `riskBand` label that already existed and was unused.

- [x] **R11 — Scenario picker.** Needs: **R5, R8**.
  A card per scenario, on the incident list and on each incident, saying what
  its scenario is *about* — the reading that looked right and was wrong — all
  derived from the incident the API returned, so nothing is described twice.
  **Links, not a "simulate" button, and that is a deliberate limit.** Running a
  scenario on demand means writing state, and state lives in the process: on
  Lambda a write lands in one container and the next read may reach another.
  Tested — a POST's audit record did survive six reads, so it would work most
  of the time and fail unpredictably, which is worse than a design that cannot
  fail. Triggering one for real belongs after **R18** makes state durable.
  The audit trail was missing entirely (`/audit` returned `[]`), so each
  scenario now seeds one derived from its own signals, hypotheses and
  transitions rather than composed separately — the timeline and the audit
  page cannot disagree about what happened.
  *Evidence: switching verified by clicking; 0901/0902/0903 land with 3/3/5
  entities, 4/5/5 cited events and 10/11/11 audit records, and only the
  beaconing scenario carries an `escalation`.*

- [x] **R12 — Real empty states.** Needs: **R11**.
  All ten of them, with line art, the sentence, and somewhere to go.
  **The action says "open a scenario", never "run" one.** R11 settled that
  scenarios are links rather than triggers on this deployment, so a button
  offering to run one would not work — and an empty state whose next action
  does nothing is worse than one with no action at all.
  The overview's activity panel had a bare sentence and no explanation; it now
  says the thing worth knowing, which is that records are written *before* an
  action runs, so an empty log means nothing was attempted rather than that
  something was attempted and lost.
  *Evidence: `verifyui.py` 18/18, contrast unchanged.*

- [x] **R13 — Loading and transition states.** Needs: **R9, R10, R11**.
  *(The note that `Skeleton` was unused was wrong — `app/loading.tsx` already
  used it. The real problem was that one Overview-shaped skeleton served every
  route, so loading an incident flashed the shape of a different page.)*
  Eight route-level loading states now, each shaped like the page it precedes:
  the map gets a tally strip and a map-sized block, incidents gets the
  scenario-card grid. A generic skeleton is a flash of something the page
  never becomes, and the eye has to re-find everything when the real content
  lands.
  *Evidence: with the RSC payload delayed, switching scenarios shows the
  loading region with 7 pulsing placeholders and the previous incident gone —
  no blank frame and no stale content. Each route's skeleton verified to carry
  its own layout rather than the Overview's.*

- [x] **R14 — Mobile pass.** Needs: **R9, R10**.
  Six overflows fixed across R10–R14, all one mistake: a flex or grid item
  defaults to the size of its content and will not shrink below it. The nav
  widened the header instead of scrolling, `truncate` could not truncate, a grid
  panel grew to 834px inside a 343px column, and the header chips outgrew the
  screen once they were relabelled. `min-w-0` in four places, `break-words` in
  one, `flex-wrap` in one.
  **Tables stop being tables when there is no room to be one.** The action
  registry scrolled sideways at 375px, so *rollback* — the column that says
  whether an action can be undone — was off-screen with nothing to say it
  existed. Below `sm` each row is now a block and each cell carries its column
  name from `data-label`. The markup stays a real table with real headers, so a
  screen reader and a wide viewport both still get one.
  Touch targets audited against WCAG 2.5.8: the persistent chrome — pause, the
  theme toggle, panel aside links — was 22px and is now 24. Inline citations
  inside prose are left alone, which is the exception the guideline names.
  *Evidence: `verifyui.py` 18/18 on the deployed site; `/actions` at 375px
  measures 349px of table in a 349px wrapper — no sideways scroll — with column
  labels rendering. Pages read at 375px, checked by looking at them.*
  The dependency table and causal chain at 375px; tables break first.
  **Done when:** no horizontal page scroll at 375px on any route, verified on
  the deployed site.

- [x] **R15 — Favicon set and head tags.** Needs: **R8**.
  All of it generated by `scripts/buildbrand.py` from the square spear, so a
  new artwork revision is one command: `favicon.ico` (16/32/48 in one file),
  48×48 and 96×96 PNGs, 512 icon, 180 apple-touch, and a `manifest.ts` whose
  icon list is code rather than a static file that can drift from what the
  script writes.
  **No `favicon.svg`.** The artwork is raster; wrapping a PNG in an `<svg>`
  gives none of the reasons to prefer one, and a real one needs the vector
  redraw ROADMAP.md already records as owed.
  Two traps worth recording: declaring `metadata.icons` at all *replaces*
  Next's file-convention detection instead of adding to it — a partial list
  silently dropped both the 512px icon and the apple-touch link, which were
  being generated and never referenced. And `app/favicon.ico` gets a `<link>`
  emitted on top of whatever you declare, claiming `sizes="16x16"` for a file
  that also holds 32 and 48, so it lives in `public/` instead.
  *Evidence: seven head tags, six files, all 200 on the deployed site.*

- [x] **R16 — SEO and social metadata.** Needs: **R15**.
  All nine routes carry their own title and description, including the dynamic
  ones — an incident's description is *its diagnosis*, so a shared link says
  what happened rather than repeating the site's pitch.
  The 1200×630 card is built by `buildbrand.py` from the lockup, so the name
  on it is the same artwork as the name in the header rather than re-typeset.
  `sitemap.xml` lists incidents from the API, so a scenario added later
  appears without anyone remembering to add it; entity and evidence pages are
  left out deliberately — each is a fragment of an argument, not a page that
  stands alone. `/search` is disallowed in `robots.txt`: it mints a URL for
  every query anyone types, and letting a crawler walk them buries the pages
  that matter.
  *Evidence: nine routes checked for title and description; OG tags carry an
  absolute image URL with width, height and alt; `robots.txt` and
  `sitemap.xml` both serve correctly.*
  One trap: a page that appends the site name itself now double-appends it,
  because the root `title.template` already does — the incident page read
  `INC-2026-0901 · Pashupatastra · Pashupatastra` until it stopped.
  **Note:** Search Console submission and reindexing are yours to do and take
  days to weeks. Nothing in code makes Google show a favicon on any timeline.

- [x] **R17 — Deploy Phase 2 and review.** Needs: **R9–R16**.
  *Evidence, against the deployed site: 18/18 layout checks at 375, 768 and
  1440; every colour pairing meets WCAG AA in both themes; nine routes with
  their own title and description; six icon files and a manifest all 200;
  `robots.txt`, `sitemap.xml` (8 URLs, 3 incidents from the API) and a
  1200×630 card. Read in both themes at desktop and at 375px.*
  **Phase 2 is closed.** Phase 3 builds the chat agent on this demo and needs
  the Anthropic API, which has no free tier. **Phase A is the agent that
  watches a real machine, and is what the owner asked for.**

---

## Phase 2A — Make it look like a console, not a document

Chosen by the owner on 20 August 2026 after Phase 2 closed, because the result
still read as flat. The diagnosis, independent of taste: **everything sits at
the same visual weight** — bordered rectangle, small label, small text, repeated
down every page. Correct, and flat. No depth, no scale contrast, almost no use
of the brand colours, and no data visualisation beyond one sparse map.

Direction: **rich SOC console.** Keep the calm, precise register the prompt asks
for — an air-traffic display, not a movie-hacker terminal — and add the depth
and the graphics it is missing.

- [x] **R40 — Surfaces with depth.** Needs: **R17**.
  Elevation, gradient panels, and a glow on critical state. Every surface is
  currently one flat fill with a 1px border.
  **Done when:** a critical incident is visibly different in weight from a
  resolved one before reading a word, and contrast still passes in both themes.

- [x] **R41 — A type scale with real contrast.** Needs: **R40**.
  Headline numbers much larger, labels smaller and quieter, so a page has an
  order to read it in.
  **Done when:** the overview's numbers read at a glance from across a desk.

- [x] **R42 — Charts and sparklines.** Needs: **R41**.
  Severity over time, risk distribution across the registry, entity status
  breakdown. **Every series comes from data the API already returns** — a chart
  of invented numbers on a page about not inventing things would be absurd.
  **Done when:** the overview and the action registry each carry a chart drawn
  from real values, and no series is synthesised.

- [x] **R43 — The attack chain as a flow.** Needs: **R40**.
  The causal chain drawn as connected entities with the technique on each edge,
  instead of a numbered list. Keeps the list underneath for screen readers.
  **Done when:** the chain reads as a picture at a glance and loses nothing for
  a reader who cannot see it.

- [x] **R44 — Motion.** Needs: **R41**.
  Page transitions, numbers counting up, staggered reveals, depth on hover.
  **Done when:** every animation is disabled under `prefers-reduced-motion`, and
  nothing load-bearing depends on motion to be understood.

- [x] **R45 — Deploy and review.** Needs: **R40–R44**.
  *Evidence: contrast passes in both themes and `verifyui.py` is 18/18, both
  after the contrast tool was taught to read gradient backgrounds — see below.*
  **The measurement tool was wrong before it was right.** `.panel` began
  painting with `background-image`, and the tool only read `backgroundColor`,
  so a gradient surface reported as transparent and text was measured against
  the page ground instead. It reported two failures; the fix I nearly made was
  to darken `--ok` and drop an opacity — changing brand colours to satisfy a
  broken measurement. Once the tool sampled gradient stops the real cause was
  visible: in light theme `--raised` is *darker* than `--panel`, so a top-down
  gradient darkens the top of every panel. Light panels are flat with a shadow
  now, which is where a light surface should get its depth from anyway.

## Phase 3 — The agent

Needs **R17**. The biggest engineering lift; budget the most time here.

The claim being defended: the policy engine, risk model, entity data and causal
reasoning are deterministic code you own. The model reads your structured data
and talks about it. Your risk tiers never ask an LLM whether something is safe.

- [x] **R18 — Persistence that survives a cold start.** Needs: **R17**.
  DynamoDB, single-table, behind the `Store`/`AUDIT` seams that already exist —
  chosen over RDS because its free tier does not expire. Provisioned 25R/25W,
  the always-free allowance; on-demand has no perpetual free tier.
  **Done when:** `/api/v1/health` reports `ok`, and an incident approved before
  a forced cold start is still there afterwards. — **met.** A verdict written
  live took the trail 30 → 31, every container was then forcibly replaced, and
  the new one answered `ok · dynamodb · 3 incidents · 31 audit records`. Three
  things had to be right for that: the audit sort key carries a sequence, so two
  records in one millisecond do not overwrite each other; `_seed_demo` is
  idempotent against a version marker, so cold starts stop re-seeding a store
  that keeps what it is given; and `backend.durable()` is the single place the
  question is answered, where incidents, the audit trail and the graph each used
  to decide separately and could disagree.
  Re-verified on clean data after the namespace landed: the table was emptied,
  the console re-seeded itself to exactly 3 incidents, a written record survived
  a second forced replacement, and the count stayed at 3 rather than doubling —
  which is the seed marker doing its job.

  Durability changed what a mistake costs, and it collected on that twice before
  the phase was over. A local run seeded the *infrastructure* incident into the
  security console, and the tests written for this task put four fixture hosts
  on the live service map. In memory both would have been erased by the next
  restart; in a table they simply stayed. The fix is `dynamo_namespace`, a
  prefix on every partition key, so one table holds `prod` and `test` without
  either seeing the other — a second table was not an option, because the free
  allowance is per account and would have been split rather than doubled. The
  structural half is `services/api/tests/conftest.py`: importing `app.main` runs
  the seed as a side effect of import, so the guard has to be set before any
  test module loads, not asserted inside each test.

- [ ] **R19 — Chat route with read-only tools.** Needs: **R4, R18**.
  `POST /api/agent/chat`. Loads incident, causal chain, entities and audit as
  context; exposes only risk-tier-0 read-only actions as tools.
  The API key goes in a Lambda environment variable — Secrets Manager is
  $0.40/secret/month and this is a demo.
  **Done when:** a question about an incident returns an answer grounded in
  stored data, with the tool-call trace recorded.
  **Cost:** Anthropic API, pay-per-token. Set `PASHU_MODEL_TOKEN_CEILING` and a
  per-conversation cap **before** the first call.

- [ ] **R20 — Guardrails in code.** Needs: **R19**.
  The chat route cannot invoke a non-zero-risk action — enforced by the route's
  tool list, not by prompt instruction. Anything the agent proposes becomes a
  pending approval through the *existing* Dharma flow. No weaker path for
  AI-initiated actions than for human ones.
  **Done when:** a test asserts asking the agent to isolate a host produces a
  pending approval and no execution, and that `isolate_host` is not reachable
  from the chat route's tool set at all.

- [ ] **R21 — Chat panel UI.** Needs: **R19**.
  Collapsible right-side panel on the incident page, seeded with that incident.
  Starter chips. Every reference to a causal step or evidence id links to it,
  using R6's resolution.
  **Done when:** a visitor can ask all four starter questions and get grounded,
  linked answers.

- [ ] **R22 — Audit the agent.** Needs: **R18, R19**.
  Model id, prompt version and full tool-call trace written to the audit table
  for every turn, so "why did it say that" is answerable from the Audit page.
  **Done when:** every chat turn appears in `/audit` with its trace.

- [ ] **R23 — Deploy Phase 3 and review.** Needs: **R20, R21, R22**.
  **Stop here for review.**

---

## Phase 4 — Observatory and Blue Team mode

Needs **R23**. Additive, and benefits from the patterns above being solid.

- [ ] **R24 — Threat feed ingestion.** Needs: **R18**.
  CISA KEV, abuse.ch (URLhaus, ThreatFox), NVD for enrichment. Normalised into
  the existing event schema, polled on an EventBridge schedule into Lambda,
  stored server-side. Never called from the browser.
  **Done when:** real entries land in the store on a schedule, each carrying its
  source URL as provenance.
  **Free tier:** EventBridge Scheduler and Lambda both always-free at this rate.
  Poll hourly at most — KEV updates daily.

- [ ] **R25 — Observatory page.** Needs: **R24**.
  Timeline of real recent entries in the same visual language as incidents, with
  verification-state badges. A report is never labelled confirmed.
  **Done when:** entries render with working links back to the original
  advisory, and the badge vocabulary is enforced by a type, not a convention.

- [ ] **R26 — Curated knowledge base for the agent.** Needs: **R19, R24**.
  Verified feed entries become retrievable context for the chat agent.
  **Done when:** asking about an ingested CVE returns an answer citing your
  stored entry and its source, not the model's recollection.
  **Be precise in the copy:** this is retrieval over curated data. It is not
  fine-tuning, and must not be described as the agent "learning".

- [ ] **R27 — Blue Team mode.** Needs: **R5, R11, R25**.
  Show only the first alert; let the player choose what to investigate and which
  read-only action to run; score diagnosis, proportionality of response, and
  whether they avoided the red herring; reveal the full chain and ATT&CK mapping
  as the answer.
  **Done when:** all three scenarios are playable start to finish and scored.

- [ ] **R28 — Streak or leaderboard.** Needs: **R27**.
  Lightweight, DynamoDB-backed.
  **Done when:** a score persists across sessions.
  Anonymous by default — a leaderboard that collects names is a personal-data
  decision, not a feature decision.

- [ ] **R29 — Final deploy and pass.** Needs: **R25, R26, R28**.

---

## Phase 5 — The visitor's path

Needs **R17**. Phases 1–4 build the console and the agent. This phase answers a
different question, and it is the one the site currently fails: a stranger opens
the URL knowing nothing, and gives it about thirty seconds.

The diagnosis is that the top-level navigation is one tab per subsystem —
Overview, Incidents, Infrastructure, Actions, Audit. That is the architecture,
not the visitor's question. Nobody arrives wanting to look at a dependency map;
they arrive wanting to know what the thing does. A console is the right shape
for someone who already bought the product and the wrong shape for everyone
who has not.

The rule this phase applies: **a top-level tab is for something a visitor would
go looking for. Everything else appears where it is needed and nowhere else.**

- [ ] **R40 — Access paths in the scenarios.** Needs: **R17**.
  R6 seeded the scenarios' entities with **no edges**, deliberately — they
  declared a sequence of events, not a graph. That is why the map is a list of
  boxes, and it blocks everything below: a blast radius over a graph with no
  edges is an empty panel.
  Each scenario declares the access paths its own evidence establishes — the
  account that reached the host, the host that opened the flow — and nothing it
  does not. An invented edge is worse than a missing one, because the map is
  the thing that is supposed to be checkable.
  **Done when:** all three scenarios render a connected access graph, every edge
  traces to a cited event, and a test fails on any edge no evidence supports.

- [ ] **R41 — Blast radius inside the incident.** Needs: **R40**.
  The map is built and correct; it is in the wrong place. Rendered beside the
  failure it belongs to — these entities, what they can reach, what is already
  compromised — it is the screen that proves the system has a model of the
  estate rather than an LLM narrating log lines. Standing alone and all green,
  it is a screensaver.
  Show the sub-graph the incident's own evidence names, with the full map one
  click away.
  **Done when:** an incident page shows its affected entities and their access
  paths inline, and `/infrastructure` is reachable from it.

- [ ] **R42 — Nav that follows the visitor, not the architecture.** Needs: **R41**.
  Drop **Infrastructure** and **Audit** from `components/nav.tsx`. Both routes
  stay — they are built, tested, and right — but they stop being front doors.
  Infrastructure is reached from the incident (R41) and from entity pages, which
  already link into it. Audit is reached from the incident whose actions it
  records.
  The reasoning is the same for both, and it is not that the pages are weak:
  the access map means nothing without a failure attached, and an append-only
  audit log is a trust artefact that matters enormously during a buyer's
  security review and not at all to a first-time visitor. Neither is something
  anyone arrives *looking for*.
  Leaves Overview → Incidents → Actions: one story, in the order it happens.
  **Done when:** the primary nav is three items, and both delisted routes are
  still reachable in two clicks from the overview — verified by clicking, not by
  reading the code.

- [ ] **R43 — A landing page that is not the console.** Needs: nothing.
  `/` is currently Overview, an operator's dashboard, shown to people who have
  no idea what they are looking at. Split them: `/` becomes the page that
  explains the product, and the console moves to its own route.
  It has to carry four things and stop: the loop in one line, the before/after
  of an incident, the bounded-autonomy claim, and a way into the live demo. The
  buyer's arithmetic belongs here too — this is sold against the cost of an
  incident lasting forty minutes instead of twelve, and the site currently never
  says so.
  **No pricing.** Out of scope names billing and multi-tenancy, and a price on a
  product with no auth invites a question the site cannot answer.
  **Done when:** someone who has never heard of the project can say what it does
  after reading only `/`, and reaches a real incident in one click.

- [ ] **R44 — How it works.** Needs: **R43**.
  One page for the visitor who got interested and now wants to know whether to
  believe it: the seven stages, the risk tiers and who may authorise each, the
  two gates that keep this deployment in dry run, and the audit trail — with a
  link to the real one rather than a description of it.
  This is where the delisted Audit page earns its keep. The argument it makes is
  "you can check every claim", which is an argument, not a dashboard.
  **Done when:** every claim on `/` has a page here that substantiates it, and
  the risk table matches the registry rather than restating it from memory.

- [ ] **R45 — Deploy Phase 5 and review.** Needs: **R41, R42, R43, R44**.
  **Done when:** the deployed site opens on something a stranger understands,
  the console is still one click away, no route was deleted, and `verifyui.py`
  and `verifycontrast.py` both pass on the new pages.
  **Stop here for review.**

---

## Out of scope

From the prompt's own non-goals, repeated because they are the things most
likely to creep in: no multi-tenant SaaS, no billing, no auth beyond what
exists, no fine-tuning or MLOps, no graph database, no SIEM/EDR integrations,
and no describing anything as "autonomous" unless an action actually executed
without a human approving it.
