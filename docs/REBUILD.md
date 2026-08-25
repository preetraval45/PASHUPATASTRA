# Rebuild — sequenced delivery plan

**From SRE demo to a live, interactive cybersecurity incident-response agent.**

Source: `pashupatastra-website-rebuild-prompt.md` in the repository root. That
document says *what* to build and why. This one says *in what order*, *what each
task depends on*, and *how you know it is done*.

## How to use this

Every task has an id — `R1`, `R2`, … for the rebuild and the polish pass that
followed it, `S1`, `S2`, … for turning it into a SaaS. Tell me **"do R7"** and I do exactly that task and stop. A task is only startable when everything in its **Needs** column
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

Every task below fits AWS free tier and Vercel Hobby. Where one does not, it is
flagged where it appears rather than discovered later.

> **Vercel Hobby is non-commercial, and Phase 7 sells something.** The moment
> this has a pricing page and a paying customer, Hobby is the wrong licence and
> the deployment has to move to Vercel Pro (~$20/month) or somewhere else. That
> is not a technical constraint and no amount of engineering removes it — it is
> the first real bill this project acquires, and it arrives with S11 rather than
> with any amount of traffic.

| Service | Allowance | Expires? |
|---|---|---|
| Lambda | 1M requests + 400k GB-s / month | **Always free** |
| DynamoDB | 25 GB, 25 WCU, 25 RCU | **Always free** |
| EventBridge Scheduler | 14M invocations / month | **Always free** |
| CloudWatch Logs | 5 GB ingest / month | **Always free** |
| API Gateway HTTP API | 1M requests / month | 12 months, then ~$1/M |
| S3 | 5 GB | 12 months |
| Cognito | 50,000 monthly active users | **Always free** |
| SES (sandbox) | 200 messages / day, verified addresses only | **Always free** |
| Vercel Hobby | 100 GB bandwidth, unlimited static | **Always free**, non-commercial — see above |

**Free, but small — which changes the design rather than the budget:**

- **Groq** (R19, the chat agent). Free with no expiry, and capped at 8,000
  tokens a minute and 1,000 requests a day. Small enough that answers are cached
  durably and outputs are bounded at 800 tokens; see R19 for what each of those
  is protecting against.
- **Oracle Cloud Always Free** (R19, the fallback). 4 ARM CPUs and 24 GB, free
  permanently, running Ollama for the requests Groq's per-minute allowance
  refuses. The only piece of the platform not on AWS, because the AWS free tier
  is a 1 GB instance and a usable model needs three to four.

**Free, and enough for the SaaS phases:**

- **Cognito** — 50,000 monthly active users, always free. Identity is where a
  SaaS usually acquires its first bill; this one does not.
- **SES in sandbox** — free, and sends only to verified addresses, which is
  enough to build and test invitations against.

**Not free:**

- Nothing, currently. The earlier plan assumed a pay-per-token Anthropic key for
  the chat agent; the owner ruled that out on 21 August 2026 and the gateway
  made it a configuration change.
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
  R50 ──► R51 ──► R52
  R53 ──► R54
  R51, R52, R53, R54 ──────────► R55 (deploy + review)

Phase 5A ─ credibility + attribution     needs R55
  R56, R57, R58 ───────────────► R59 (deploy + review)

Phase 5B ─ satisfying to operate         needs R59
  R58 ──► R60 ──► R66
  R56 ──► R61
  R43 ──► R62      R51 ──► R63      R27 ──► R64      R20 ──► R65
  R60..R66 ────────────────────► R67 (deploy + review)

Phase 5C ─ Sati, deeper                  needs R59, R21
  R21 ──► R68 ─┬──► R69
               ├──► R70 ──► R71
               ├──► R72
               └──► R73
  R68..R73 ────────────────────► R74 (deploy + review)

Phase 5D ─ the capability menu           needs R74   ← a menu, not a checklist
  R75 ──► R81      R23 ──► R76 ──► R78      R71 ──► R77
  R70 ──► R80      R20 ──► R79      R26 ──► R82, R83      R50 ──► R85
  R84 is held behind S2 on purpose — per-user history needs accounts
  whichever were chosen ───────► R87 (deploy + review)

Phase 6 ─ tenancy and identity           needs R18, R59, R55
  S1 ──► S2 ──► S3 ──► S4 ──► S5        the order is not negotiable:
                       S3 ──► S6        tenancy before sign-in, scoping
                                        before invitations

Phase 7 ─ the product surface            needs S4
  S4, R53 ──► S7 ──┬──► S8
                   ├──► S9 ──► S10 ──► S11
                   └──► S12

Phase 8 ─ operating it as a service      needs S10
  S10 ──► S13 ──► S14
  S7 ─────────► S15
  S5, S8, S11, S14 ────────────► S16 (deploy + review)
```

**Three numbering notes.** `R40`–`R45` appeared twice — Phase 2A, delivered, and
Phase 5, not started — so Phase 5's are now `R50`–`R55`. Two tasks with one id
is a plan that cannot be pointed at. The SaaS phases use `S` rather than
continuing the `R` sequence, because they are a different kind of work: `R` is
"rebuild this demo into a console", `S` is "turn the console into something a
stranger can sign up for". The polish pass of 24 August 2026 continues the `R`
sequence at `R56` and hangs its phases off Phase 5 as **5A–5D**, the way Phase
2A was inserted after Phase 2 — renumbering Phases 6–8 would have invalidated
every `S` dependency written against them for the sake of tidier arithmetic.

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
  **Phase 2 is closed.** Phase 3 builds the chat agent on this demo, on free
  model providers — Groq, with Ollama on Oracle behind it. **Phase A is the agent that
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

- [x] **R19 — Chat route with read-only tools.** Needs: **R4, R18**.
  `POST /api/v1/agent/chat`. Loads incident, causal chain, events and audit as
  context; offers only read-only tools.
  **Done when:** a question about an incident returns an answer grounded in
  stored data, with the tool-call trace recorded. — **met, live on the deployed
  API.** "What happened, and which account was targeted?" against
  `INC-2026-0901` returns the credential-stuffing account takeover, naming
  `j.rivera` and the source address, citing four chain steps and two audit
  entries, every ref resolvable through R6's evidence route.

  **No Anthropic, and no pay-per-token anywhere.** Owner decision, 21 August
  2026. The model is reached through the AI Gateway as rule 5 already required,
  so this was configuration rather than a rewrite:

  - **Groq free tier** is the primary — `openai/gpt-oss-20b`, roughly 2 seconds
    a turn, 8,000 tokens per minute and 1,000 requests per day, free with no
    expiry. `openai-compat` speaks plain chat-completions, which is also what
    Ollama, vLLM, LM Studio and OpenRouter speak, so the provider is one class
    and the vendor is a base URL.
  - **Ollama on an Oracle Always Free ARM box** is the fallback — 4 CPUs and
    24 GB, free permanently, no quota, and slow. The pair is chosen for how
    their limits differ, not for redundancy: Groq fails under a burst, the box
    is too slow to lead. `scripts/oracle-ollama.sh` provisions it, behind HTTPS
    and a bearer token, because an unauthenticated LLM on a public address is
    found by scanners within days.
  - **AWS was considered and rejected for this one thing.** Ollama needs 3–4 GB
    for a usable model; the AWS free tier is a 1 GB instance, and one that fits
    is about $30/month. Oracle's free shape is 24 GB. The rest of the platform
    stays on AWS.

  Three things carry the grounding, and none of them is the prompt:

  - **Retrieval is deterministic.** Context is assembled before the model is
    asked anything; tools fetch *more*, never the basics. If grounding depended
    on the model choosing to retrieve, the model choosing not to would produce
    an ungrounded answer that looks exactly like a grounded one — and the
    fallback box, whose small model has no tool support at all, would have
    nothing to say.
  - **Citations are verified, not trusted.** Every ref is matched against what
    was actually retrieved this turn. Unmatched refs are dropped and reported in
    `dropped_refs`, and an answer left with none is returned `grounded: false`.
    Matching is exact, so `INC-2026-0901#chain-9` does not resolve against
    `INC-2026-0901`.
  - **The visitor's message is untrusted.** It is fenced and labelled like
    evidence rather than placed in the instruction channel, and fence lookalikes
    in it are neutralised. It reads like the trusted half — it is the reason the
    call is happening — which is what makes interpolating it into instructions a
    one-line mistake.

  **Cost control, since a free tier is a small tier:**
  - `chat_answer_tokens` caps output at 800. The gateway's 16,000 default is
    sized for a reasoning call, and providers count `prompt + max_tokens`
    against the rate limit — leaving it asked a free tier for 17,938 tokens to
    answer a question whose evidence was 640, and was refused in a way that
    reads like the context was too large when it was the reservation.
  - `chat_token_ceiling` bounds a whole conversation, separately from the
    per-incident ceiling. A public text box is a different exposure from an
    analyst's investigation.
  - **Answers are cached, durably.** Most questions on a public console are the
    same question. A repeat costs nothing and hits no rate limit — verified live
    at 0.01s across separate Lambda invocations, which works only because R18
    made the store durable. The key covers the incident, question, model,
    instructions and evidence, so a change to any of them retires the entry
    rather than serving a stale answer.

  A rate limit reaching a visitor is now a plain sentence and a 429. It used to
  be the provider's own body, which carries the organisation id and a billing
  upgrade link — on a public endpoint.

- [x] **R20 — Guardrails in code.** Needs: **R19**.
  The chat route cannot invoke a non-zero-risk action — enforced by the route's
  tool list, not by prompt instruction. Most of this landed with R19 and is
  tested: a tool the model was not offered is never dispatched, the trace
  records the attempt as a refusal, and the offered list is *derived* from
  `ActionSpec.read_only` rather than written by hand.
  **Done when:** a test asserts asking the agent to isolate a host produces a
  pending approval and no execution, and that `isolate_host` is not reachable
  from the chat route's tool set at all. — **met, and confirmed live.** Asking
  the deployed console to isolate the host returns `proposed_action_id:
  isolate_host`, a Dharma verdict of `senior` at risk 67 requiring a
  `senior_operator`, an approval id, and an audit line reading *proposed
  isolate_host: risk 67 → senior, awaiting a human*. Nothing executed.

  The agent names an action; it never holds one. Two locks decide what it can
  touch and both must agree — `ActionSpec.read_only` says a thing is a read,
  and `AgentSpec.may_use` says this agent was given it — so marking something
  read-only by mistake does not reach a public text box on its own. A proposed
  id is checked against the registry before it goes anywhere, the same
  discipline citations get: a model naming `quarantine_host` (plausible, not an
  action here) would otherwise queue an approval for something that cannot be
  executed, reviewed or rolled back. Proposals are never served from cache,
  because a cached copy would answer "queued for approval" without queueing
  anything.

  **A correction worth recording.** The first version passed
  `agent_risk_limit=0`, reading as the cautious choice. It forces `DENIED`, and
  `/policy/approve` refuses a denied verdict — so every proposal dead-ended
  exactly where this task wants it to reach a human. The flag answers "may this
  agent act alone", which is always no here; using it to answer "may a human
  approve this" conflates the two. Proposals are now scored exactly as a
  person's request is, which is also the plainest reading of *no weaker path
  for AI-initiated actions than for human ones*: it is the same path. What stops
  the agent acting is structural — the route has no execute path, and no
  risk-bearing action is in its tool set.

  R19 found the predicate in this task was wrong. `changes_nothing` is true of
  `notify_analyst`, which pages a human being, and of `create_case`, which
  writes a record — both risk 0. Read-only is now declared on the action rather
  than inferred from its risk, because the two questions are opposites:
  `changes_nothing` widens what may run unattended, `read_only` narrows what may
  be handed to a model. Deriving the second from the first would have put "page
  the on-call analyst" behind an unauthenticated text box. Anything the agent proposes becomes a
  pending approval through the *existing* Dharma flow. No weaker path for
  AI-initiated actions than for human ones.
  **Done when:** a test asserts asking the agent to isolate a host produces a
  pending approval and no execution, and that `isolate_host` is not reachable
  from the chat route's tool set at all.

- [x] **R21b — A navbar that survives being narrow.** Needs: **R21**.
  Five links, a search box and a status group do not fit on one line below a
  laptop. The previous answer was an `overflow-x-auto` strip with the scrollbar
  hidden, which is why every layout check passed: nothing was missing from the
  DOM and nothing overflowed its container. But at 768px only *Overview* was on
  screen — no scrollbar, no fade, no affordance — and a visitor with a mouse
  could not reach Incidents at all.
  **Done when:** every section is reachable at 375, 768, 1024 and 1280, and the
  header is one row at each. — **met, on the deployed site.** Links become a
  menu below `lg`, the search becomes an icon below `sm`, and the freshness
  clock drops at `2xl`. Header height went from 129px to 57px on a phone. 18/18
  layout checks pass.

  Navigation and execution mode never disappear — they move into the menu,
  which is a place, rather than into an overflow, which is not. Someone reading
  on a phone has the same right to know whether an approval would change
  production.

  **`verifyui.py` now counts what a person can see and click**, not what exists
  in the DOM. The old check could not have caught this, and did not: eighteen
  green ticks while the site could not be navigated. A checker that passes while
  the thing it checks is broken is worse than no checker, because it is trusted.

- [x] **R21 — Chat panel UI.** Needs: **R19**.
  Collapsible panel on the incident page, seeded with that incident, with
  starter chips and every citation rendered as a link.
  **Done when:** a visitor can ask all four starter questions and get grounded,
  linked answers. — **met.** `scripts/verifychat.py` drives the panel in a real
  browser against the deployed API: four *distinct* answers carrying 4, 13, 1
  and 9 citations, every one resolving, none dropped, all grounded. 18/18 layout
  checks still pass with the panel in place.

  Placed under the incident rather than beside it. A right-hand rail is the
  conventional shape and the wrong one here: at 375px it becomes a bottom sheet
  covering the thing being asked about, and the questions are *about* what the
  reader just read. Collapsed by default, because an assistant that opens itself
  is something to dismiss before reading the incident.

  **Citations needed a resolver, not the existing one.** `Evidence` sends every
  ref to `/evidence/`, which is right only for event ids; a causal step or an
  audit record sent there 404s. A citation that leads to "not found" is worse
  than one plainly unlinked — it looks checkable, and checking it fails. So
  `hrefFor` routes each kind to a real target, and the chain, plan and diagnosis
  gained anchors to land on.

  **Audit refs had to stop being positional.** They were `audit#2`, an index
  into a newest-first list — and answering a question appends an audit record,
  so by the time the page rendered, index 0 was the chat turn that produced the
  citation. Refs are now keyed by timestamp, with a second anchor on each row.

  **The verification lied twice before it worked**, which is the part worth
  keeping. First it located turns by counting `<p>` elements and read the
  visitor's own question back as the reply — four green ticks, nothing tested.
  Then, fixed, it fired the questions back to back, hit the per-minute token
  allowance, and reported one answer four times. It now finds turns by data
  attribute, paces itself under the allowance, and **fails on identical
  answers**, because four questions returning one answer would satisfy every
  other check while proving nothing.

- [x] **R22 — Audit the agent.** Needs: **R18, R19**.
  **Done when:** every chat turn appears in `/audit` with its trace. — **met, on
  the deployed site.** Each turn is an `agent_turn` record carrying the
  question, the answer, the model, the provider, the prompt version *and its
  digest*, the citations, and every step the agent took. The audit page renders
  it behind a "why it said that" expander.

  A chat turn is its own kind of record. An observation is something the
  platform saw; a turn is something it *said*, and filed together the agent's
  turns vanish into a trail of telemetry.

  The prompt version is written by hand and therefore wrong exactly when
  someone edits the prompt and forgets to bump it — the case a reader most needs
  to notice — so a digest of the instructions goes with it. Two turns claiming
  version 2 with different digests are visibly not the same prompt.

  Cached turns are recorded too, carrying the cost and trace of the run that
  produced the answer. A cache hit is still an answer given to someone, and a
  trail that skipped them would show questions with no replies.

  **The visitor's question is capped and stripped of control characters before
  it is stored**, and kept out of the summary line. It is text a stranger typed
  into a public box, on its way to an append-only record on a public page.

  **This phase found the cache had never worked.** R21 made audit refs
  timestamps; answering appends an audit record; the refs were in the cache key
  — so the key changed on every request and nothing was ever served from cache.
  It was invisible, because a cache that always misses still returns correct
  answers, at full price. On an 8,000-token-a-minute allowance that is the
  difference between serving a burst of visitors and refusing them. `/health`
  now reports `chat_cache` so it cannot fail silently again.

  The audit trail was removed from the evidence entirely. It caused three
  problems with one root — the trail moves while the page does not: citations
  that could never resolve, a cache key that changed every request, and the
  agent reading its own previous replies as observed fact. Nothing of substance
  is lost; the plan steps carry the verdicts, as refs that stay put.

  **Free-tier tuning, measured rather than assumed.** `gpt-oss` bills reasoning
  as output: 326 output tokens at `high` effort against 43 at `low`, same
  answer. These replies summarise evidence already retrieved and assembled, so
  the reasoning was being paid for and thrown away. A live turn went from 6,584
  tokens to 4,869, and the provider drops the setting by itself on an endpoint
  that does not know it.


- [x] **R23 — Deploy Phase 3 and review.** Needs: **R20, R21, R22**.
  Deployed and verified against `https://pashupatastra.vercel.app`.

  *Evidence: 21/21 layout and reachability checks at 375, 768 and 1280. All four
  starter questions answered with distinct, grounded replies carrying 7, 9, 1
  and 1 citations, every one resolving. Asking it to act returns
  `isolate_host`, a verdict of `senior` at risk 67 needing a `senior_operator`,
  an approval id, and nothing executed. Every turn is in `/audit` with its
  trace. `/health`: `ok · dynamodb · chat_cache durable`. 697 tests, ruff clean,
  WCAG AA in both themes.*

  **What Phase 3 actually built.** An agent that answers from the store and
  cannot act. Three properties carry that, and none of them is the prompt:
  retrieval is deterministic, so a model that never calls a tool still answers
  from real data; citations are verified against what was retrieved, so an
  invented ref is dropped and the answer marked ungrounded; and the tool set is
  derived from `ActionSpec.read_only` intersected with `AgentSpec.may_use`, so
  `isolate_host` is absent because of what it is, not because someone remembered
  to exclude it.

  **The recurring lesson of this phase was that checks lie.** Four times a green
  result meant nothing: `verifychat` read the visitor's own question back as the
  reply; then it read the previous answer when a question was rate-limited;
  `verifyui` passed 18/18 while the navbar was unnavigable at 768px; and the
  answer cache reported nothing wrong while missing on every single request,
  because a cache that always misses still returns correct answers. Each fix was
  the same shape — **count what changed, not what is present** — and each was
  found by looking at the deployed site rather than at the suite.

  ### Known weaknesses, stated rather than discovered later

  - **The free tier is 8,000 tokens a minute.** A turn costs ~4,900, so a burst
    of visitors gets a 429 and a polite sentence. The cache makes repeats free,
    which covers the starter questions; anything novel competes for the window.
    `scripts/oracle-ollama.sh` provisions the unlimited fallback and **has not
    been run**, so today a rate limit is a refusal rather than a slower answer.
  - **The security topology has no edges.** Eleven nodes, zero dependencies, so
    the map draws no connections and blast radius has nothing to traverse —
    `0 observed access paths` is truthful and looks broken. The scripted
    scenarios never asserted a dependency; adding them is data, not code.
  - **Map severity now blends telemetry with open incidents.** Defensible — an
    entity is shown as the most serious thing currently true about it — but it
    is a display rule layered on top of a windowed measurement, and the two
    should probably become one explicit concept.
  - **The Groq key was pasted into a chat window on 21 August 2026.** Rotate it.
  - `next start` cannot serve this app from a OneDrive path on the owner's
    machine (the `[id]` chunk 400s and nothing hydrates). `next dev` works, and
    the deployed build is unaffected — but it will cost someone an hour.

---

## Phase 4 — Observatory and Blue Team mode

Needs **R23**. Additive, and benefits from the patterns above being solid.

- [x] **R24 — Threat feed ingestion.** Needs: **R18**.
  **Done when:** real entries land in the store on a schedule, each carrying its
  source URL as provenance. — **met.** 24 real entries stored: CISA KEV
  advisories added the day before, and live URLhaus submissions, each with a
  working link to the original. A forced cold start re-ran it and stored **0**,
  because the cursor is in DynamoDB. `pashupatastra-feeds` is `ENABLED` at
  `rate(1 hour)`.

  *The schedule was proved by watching it fire, not by reading its
  configuration. Tightened to `rate(5 minutes)` with the flexible window off, it
  invoked the function at 17:21:13Z on its own — the log line is there and
  nobody ran it — and it was restored to hourly afterwards. "Created" and
  "fires" are different claims, and only the second one is the task.*

  **A permission was granted to finish this**, and it is worth naming: the
  deploying user could not create schedules. `PashupatastraPlatform` gained two
  statements — `scheduler:*` on `schedule/default/pashupatastra-*`, and
  `iam:PassRole` on the scheduler role alone, conditioned on
  `iam:PassedToService = scheduler.amazonaws.com`. Both are narrower than the
  wildcards already in that policy. The condition matters: a `PassRole` without
  it lets the role be handed to any service that will take it, which is how a
  scoped `PassRole` turns out not to be scoped.

  **ThreatFox is deliberately absent.** abuse.ch now requires an API key for it.
  A key nobody has is a dependency that fails in production and passes in every
  test written around it, so the feed is left out rather than half-wired.

  **`Verification` is a closed vocabulary**, not a free-text field: CISA is
  `confirmed` because its entry criterion is evidence of exploitation; URLhaus
  is `reported`, always, because those are community submissions the publisher
  does not assert. Rating an unreviewed submission as highly as observed
  exploitation is the mistake this exists to prevent, and it is enforced by
  ordering (`RANK`) so anything sorting by weight gets it right.

  **Intelligence is never a topology node.** These describe the world, not this
  estate. `VULNERABILITY` and `INDICATOR` are referenced by events and never
  upserted as nodes — a map drawing a thousand CVEs beside eleven hosts says
  they are the same kind of fact, and blast radius would traverse from a host
  into a vulnerability as though the two were connected. A test asserts the node
  count does not move when a feed is ingested.

  **The malware URL is never rendered.** URLhaus entries are keyed by host, and
  the link a reader follows is the advisory *about* the URL. A console that
  renders live distribution points as anchors is one that eventually gets
  clicked.

  Two things this found: `recent_events` returned rows exactly as stored, which
  published the table's own `PK`/`GSI1PK` — including the namespace — and left
  three fields as JSON strings for callers to parse. The normaliser every other
  read already used was the fix, and a test now covers every read path. And the
  first severity mapping made ransomware-linked and ordinary advisories
  identical; ransomware use is what separates urgent from important, so it
  decides severity rather than sitting in the payload for a reader to notice.
  **Free tier:** EventBridge Scheduler allows 14M invocations a month; hourly
  polling uses 720. Poll no faster — CISA publishes daily.

- [x] **R25 — Observatory page.** Needs: **R24**.
  **Done when:** entries render with working links back to the original
  advisory, and the badge vocabulary is enforced by a type, not a convention. —
  **met, on the deployed site.** 25 entries across two feeds, grouped by the day
  the source published, every one carrying a link to the advisory. Filtered to
  CISA: 12 entries, 12 `confirmed`, 0 `reported`, each linking to its NVD page.
  24/24 layout and reachability checks; WCAG AA in both themes.

  **The vocabulary is a closed union with a `Record` over it**, so a fourth
  verification state arriving from the API without a decision about how it looks
  is a compile error rather than a badge that renders blank. An unrecognised
  value shows as `unverified` — falling back to the friendliest state is how
  "nobody checked this" quietly becomes "fine".

  **`reported` is deliberately not green.** Green on an unverified malware
  report reads as "checked, and fine", which is the opposite of what it says.
  Neutral is the honest colour for a claim nobody has stood behind. `confirmed`
  takes the strongest colour on the page, because CISA listing something as
  exploited in the wild is the most load-bearing statement here.

  **Facts differ per source because they are different.** A KEV entry has a
  federal remediation deadline and may be tied to ransomware; a URLhaus entry
  has neither and has liveness instead. One shape for both would mean empty
  columns or facts dropped from whichever source lost the argument.

  Per-feed cursors are on the page. A feed that has quietly stopped looks
  exactly like a quiet feed, and on a page whose entire claim is freshness that
  is the failure worth showing. External links carry `rel="noopener noreferrer"`
  — the referrer would otherwise tell an advisory site which console is reading
  about which attack.

- [x] **R25b — A header that is quiet when nothing is wrong.** Needs: **R25**.
  The chrome carried `env dev · dry run · nothing executes · updated just now`
  on every page of a deployment that is permanently in dry run. Owner decision,
  21 August 2026, and the right one: **a warning that is always present is one
  nobody reads.**

  Not deleted — inverted. The fact it carries is whether an approval would
  change production, which matters enormously in one state and not at all in the
  other, so it is now shown in one state and not the other. `LIVE EXECUTION` is
  louder for having nothing beside it, and `memory only` still appears when the
  store is not durable. The freshness clock went entirely: the page already says
  when it was updated, which is why that chip was the first thing dropped at
  every breakpoint.

- [x] **R26 — Curated knowledge base for the agent.** Needs: **R19, R24**.
  **Done when:** asking about an ingested CVE returns an answer citing your
  stored entry and its source, not the model's recollection. — **met, and the
  second half is the part that was actually tested.**

  Asked about `CVE-2026-69836`, which the hourly poll had ingested, it answered
  from the stored advisory — Microsoft Entra ID, deserialization, catalogued
  2026-08-21, federal deadline 2026-08-24 — citing the stored event id, grounded,
  nothing dropped.

  Then asked about `CVE-2021-44228`, which is **not** in the store and which
  every model of this generation knows by heart: *"I have no stored advisory for
  CVE-2021-44228 in the evidence repository, so I cannot provide details about
  it or its severity."* `answerable: false`, cited nothing, and not one of
  Log4j, Log4Shell, JNDI or LDAP in the reply. That is the test that separates
  retrieval from recollection — the first result alone would have proved only
  that retrieval agreed with what the model already thought.

  **Retrieved before the model is asked, not by the model choosing to look.** A
  model asked about a CVE already has an opinion, and an opinion is what it
  gives when nothing better is in front of it. Identifiers in the question are
  resolved up front, so the grounded answer is the easy one rather than the
  disciplined one. A `lookup_advisory` tool exists on top of that, for
  identifiers the question did not name.

  **An unknown identifier produces no evidence block at all.** The tempting
  alternative — a block reading "nothing on file for CVE-X" — hands the model a
  ref to cite for a claim about nothing, and produces an answer that looks
  grounded while resting on an absence. The instructions cover the missing case
  in words instead.

  **The extraction pattern is deliberately narrow.** Only `CVE-\d{4}-\d{4,7}`,
  word-bounded. A looser one — hostnames, addresses — would turn every question
  into a lookup of whatever string it contained, and on a public console that is
  an interface for asking which of *our* entities exist. A CVE id is a public
  identifier for a public document, so resolving one gives away nothing. The
  tool validates against the same pattern rather than passing its argument
  through, because otherwise `account:j.rivera` is a valid argument.

  Prompt version moved to **3**, which retires every answer cached under 2. The
  version is written by hand and the digest goes with it, so an edit that
  forgets the bump is still visible (R22).

  **The copy says retrieval, and nowhere says learning.** No weights changed and
  nothing was fine-tuned; a curated corpus is read at question time. Checked
  across the site and the agent — the only "Learn" on the site is the platform's
  own `Observe → … → Learn` loop, which is a different claim and predates this.

- [x] **R27 — Blue Team mode.** Needs: **R5, R11, R25**.
  **Done when:** all three scenarios are playable start to finish and scored. —
  **met, verified in a browser against the deployed site.** All three listed,
  played, and marked: exactly one explanation scores the diagnosis marks in each,
  the investigation marks move from 20 to 0 when nothing is opened, and the
  reveal and the wrong-answer explanation both appear every time. 27/27 layout
  checks; 51 engine tests across the three scenarios.

  **The answer stays on the server.** The briefing carries the opening alert,
  the entities, the candidate explanations and the action menu — and no
  confidence, no contradictions, no chain, no technique mapping, no plan. A page
  that ships its own solution teaches the player to open dev tools, and the
  thing being taught here is how to read evidence. Only the attempt returns the
  answer.

  **Scored on three dimensions because incidents fail on three.** A player can
  name the right cause and reach for a sledgehammer; can pick the proportionate
  action for the wrong reason; and can be right by luck, never having opened the
  evidence that rules out the plausible alternative. That last one is what the
  exercise is really for, because the plausible alternative is what a tired
  analyst takes at 3am.

  **Two bugs found by building it, both of the same kind — a thing that looks
  fine and cannot be won.**

  - The action menu was the registry sorted by risk, first eight. That left
    `isolate_host` off the list for a beaconing workstation: the correct answer
    was not on offer, so the response dimension could not score above a third,
    and nothing said so. The menu is composed now — the plan's actions,
    something that does too little, something that does far too much, and
    plausible middle ground.
  - Excluding rollbacks by *being some action's `rollback_action_id`* removed
    `isolate_host`, `block_ip`, `revoke_session` and `quarantine_email` — every
    correct answer. The relationship is **mutual**: `isolate_host` names
    `rejoin_network` as its rollback and `rejoin_network` names `isolate_host`
    as its, so there is no direction to read. What can be identified is
    narrower and is the only exclusion worth making: the inverse of what *this*
    plan calls for.

  **The checker does not know the answers, and must not.** The first version
  guessed — it picked the last option and called that the careful attempt — and
  reported two scenarios broken because its guess was the decoy. It was
  measuring itself. It now submits *every* explanation and asserts exactly one
  scores, and isolates the investigation dimension by changing only whether the
  evidence was opened. Both are checkable from outside without a second copy of
  the truth to drift.

- [x] **R28 — Streak or leaderboard.** Needs: **R27**.
  **Done when:** a score persists across sessions. — **met, twice over.** A
  scenario was played, the browser context was destroyed, and a new one carrying
  only the token read the record back. Then every Lambda container was forcibly
  replaced and the record was still there, `durable: true`, straight out of
  DynamoDB.

  **A streak, not a leaderboard, and that is the whole design.** A leaderboard
  with names is a system that collects names: it needs a retention answer, a
  deletion path, a moderation policy for what people type into it, and a line in
  a privacy notice. None of that is worth acquiring so that a training exercise
  can say "well done".

  So there is no name and no account. The browser generates an opaque UUID,
  keeps it locally, and sends it with an attempt. The server can tell that two
  attempts came from the same browser and nothing else. Four things make that a
  property rather than a promise:

  - **The token is validated to a UUID shape.** Without it the identifier is an
    arbitrary string that becomes a sort key, and it would store
    `alice@example.com` quite happily the first time anyone sent one. The shape
    is what makes "this holds no personal data" structural.
  - **There is no route that lists players.** The absence is the feature: an
    enumerable set of scores *is* a leaderboard. A token can read only itself.
  - **The token is not in the audit line.** The trail is public, and a
    pseudonymous id printed beside a timestamp on a public page is a thing that
    can be correlated.
  - **The page never mints one.** `readPlayer` on render, `ensurePlayer` on
    submit. A page that creates an identifier because it loaded has decided on
    the visitor's behalf, and a first-time visitor sees no mention of tokens,
    storage or streaks at all.

  Clearing the token *is* the deletion path, not a request for one — with
  nothing to join them to, the orphaned rows are not a record of anybody. The
  button is on the page and was tested: token gone, record gone after reload.

  **The score is computed on the server and never accepted from the client.** A
  number a player can choose is not a score, and a test asserts the request
  model carries choices and a token and nothing resembling a total. Best per
  scenario is a maximum rather than the last result — a player who scores 100
  and then experiments with a deliberately wrong answer has not got worse at it
  — while the streak breaks below `sound`, because a streak that survives a
  wrong diagnosis measures persistence rather than competence.

- [x] **R29 — Final deploy and pass.** Needs: **R25, R26, R28**.
  Deployed and reviewed. **Phase 4 is closed — R24–R29 all done.** What remains
  is Phase 5 (the visitor's path, R50–R55), the SaaS phases (S1–S16), and Phase
  A, the agent that watches a real machine.

  *Evidence, against `https://pashupatastra.vercel.app`: 27/27 layout and
  reachability checks at 375, 768 and 1280; WCAG AA in both themes; all four
  chat starters grounded with every citation resolving; all three blue team
  scenarios playable, with exactly one explanation scoring per scenario and the
  investigation marks moving when evidence is opened; 916 tests; ruff clean;
  the deployed API and the committed OpenAPI spec agree on all 27 routes.*

  **A pass means trying to break it, not re-running green checks.** What that
  found:

  - **The committed `openapi.json` was eight routes stale** — the entire chat
    and game surface. Nothing noticed because nothing was looking. A stale spec
    is worse than none: it describes a system that no longer exists and the
    reader cannot tell. Regenerated, and `testapi.py` now compares the committed
    paths against the live app. Confirmed the test fails on the old spec before
    trusting that it passes on the new one.
  - **The not-found page named a console that no longer exists** — "Overview,
    Incidents, Infrastructure, Actions, and Audit", written before Ask,
    Observatory and Blue team. It no longer lists the sections at all; the
    navigation above it is already that list and cannot drift from itself.
  - **A comment in `timeline.tsx` still called the audit trail "in-memory and
    per-process today"**, which stopped being true at R18.
  - **`verifychat.py` sampled once after `networkidle`** and reported the chat
    panel missing from a page that plainly had one. It waits for the panel now.
    `networkidle` means the network went quiet, not that the page finished.

  Probed and correct: every error path returns the right status (404 for unknown
  feeds, scenarios, incidents, events and entities; 400 for a malformed player
  token); the game refuses entities from other incidents, entities that do not
  exist, intelligence keys and path traversal alike; the briefing leaks none of
  confidence, contradictions, chain, technique or plan; both themes render
  without overflow at 375px on every page added this phase; the sitemap covers
  the new routes and the hourly feed schedule is still `ENABLED`.

  **One characteristic, stated rather than left to be discovered.** The console
  publishes the full incident — chain, confidence, plan — at
  `/incidents/{id}`, and the blue team scenarios *are* those incidents. A player
  who wants the answer can read it there. That is deliberate: hiding them would
  break the console, which is the product, and this is a teaching exercise
  rather than an examination. What R27 protects is narrower and worth having —
  the answer is not in the page you are playing on.

  **Also known:** `notFound()` returns HTTP 200 on these routes rather than 404.
  The rendered page is correct and a visitor sees the right thing; the status is
  wrong because the layout streams before the page resolves. It affects
  crawlers, not readers, and the sitemap lists only real ids. Left for a later
  task rather than restructured at the close of a phase.

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

- [x] **R50 — Access paths in the scenarios.** Needs: **R17**.
  **Done when:** all three scenarios render a connected access graph, every edge
  traces to a cited event, and a test fails on any edge no evidence supports. —
  **met, live.** The map draws 11 entities and 10 access paths, each carrying
  the event ids that establish it, and blast radius now answers:
  `host:ws-0148` reaches `fs-02`, `app-07` and the scheduled task;
  `account:j.rivera` reaches `sso-portal`; `account:m.okafor` reaches the
  mailbox and the OAuth application.

  **The old decision was right about the danger and wrong about the remedy.**
  The seed added no edges at all, reasoning that a topology drawn from
  co-occurrence would put fabricated structure behind blast radius. True — and
  the result was a row of disconnected boxes, an empty blast radius, and
  `isolate_host` pricing its risk against an estate of one. The answer is not
  "no edges" but **no edge without a citation**.

  `Edge` gained an `evidence` field, because an edge is a claim — *this account
  could reach that asset* — and rule 1 says a claim carries a reference. Each
  path names the signals that establish it and no others: the flow reaching the
  portal is `SEC-0001-a`; the flow authenticating as an account is `SEC-0001-b`;
  the session on the portal is `SEC-0001-d`. `SEC-0003-c` establishes two edges
  at once, which is why evidence is a list rather than one id.

  **Direction is the thing that would have been silently wrong.** `blast_radius`
  walks dependents, so the edge runs from the asset *to* the account —
  compromise flows target to source. It reads backwards to anyone thinking
  "access goes account → asset", and reversed it would report that compromising
  a mailbox endangers the attacker, with every risk score built on it wrong
  while still looking like a number. A test pins the direction on the phishing
  scenario in both directions.

  **The citation nearly did not survive storage.** `upsert_edges` wrote source,
  target and kind, so the edge would have reached DynamoDB and its reason would
  not — the checkable property working on a laptop and nowhere else. Both stores
  persist and return it now.

  `testaccesspaths.py` enforces the rule and was watched failing before being
  trusted: an uncited edge is caught as *cites nothing*, and one citing a ref
  from another scenario as *not one of this scenario's signals*.

- [x] **R51 — Blast radius inside the incident.** Needs: **R50**.
  **Done when:** an incident page shows its affected entities and their access
  paths inline, and `/infrastructure` is reachable from it. — **met, live.**
  Every incident carries a *What this reached* panel: the C2 channel into
  `ws-0148`, out to `app-07` and `fs-02`, and on to the scheduled task —
  5 entities, 4 access paths, with *the whole map →* beside the heading.

  **The map was extracted rather than redrawn.** `/infrastructure` had 337 lines
  with the SVG inline; a second copy for the incident page would have been
  quicker and would have drifted, and the half that drifts is always the one
  drawn less often — which here is the one an operator reads *during* an
  incident. `components/accessmap.tsx` now serves both, so someone who has
  learned to read the map on the whole estate does not have to learn it again on
  one incident.

  **Only what the incident's evidence names.** An edge is drawn when both ends
  are in the incident. A path from one of these entities out to something the
  incident never mentions is real and is not drawn — that would say the incident
  reached further than its evidence establishes, which is R50's rule about
  inventing edges applied to borrowing them. What lies beyond is counted instead
  and listed in words: `reachable beyond it · 0` is a finding, and it reads very
  differently from an absence.

  **Filtered server-side.** The alternative ships the whole estate to draw three
  nodes, which works at eleven entities and stops working at the first real
  deployment — and this is the one screen that has to load while somebody is
  waiting.

  Two things this turned up. The marker id had to be per-map: two maps on one
  page sharing `#arrow` means the second one's arrowheads resolve to the first
  one's definition, which works right up until the first is conditionally not
  rendered. And **the R29 OpenAPI drift test earned its place immediately** —
  adding `/incidents/{id}/graph` failed the suite before the route reached a
  browser, which is exactly the job.

  *Known and not invented: every entity carries `estimated_users: 0`, so blast
  radius reports entity counts truthfully and user impact as zero. The counts
  are real; the user figure is absent rather than wrong, and inventing one is
  precisely what R50 forbids.*

- [x] **R52 — Nav that follows the visitor, not the architecture.** Needs: **R51**.
  **Done when:** the primary nav is three items, and both delisted routes are
  still reachable in two clicks from the overview — verified by clicking, not by
  reading the code. — **met on the substance; the count was applied as a rule
  rather than a number.**

  Infrastructure and Audit are out of the navigation, for the reasons the task
  gave: the access map means nothing without a failure attached, and an
  append-only audit log matters enormously during a buyer's security review and
  not at all to someone who arrived thirty seconds ago. Neither is something
  anyone *arrives looking for*.

  **The nav is six, not three, and that is deliberate.** "Three" was written
  when there were five sections. Phases 3 and 4 added Ask, Observatory and Blue
  team, and each survives the same test the other two failed — *would a stranger
  go looking for this?* Can I ask it something, is any of this real, can I try
  it myself: yes, yes and yes. Applying the number instead of the rule would
  have deleted three sections for arithmetic.

  **`scripts/verifyreach.py` drives a real browser**, because the task said
  verified by clicking and a link that exists in the source but is covered,
  disabled or scrolled away is not a link. It found two things nothing else
  would have:

  - **The audit trail was not reachable from an incident at all.** The reasoning
    for delisting it was that it is "reached from the incident whose actions it
    records" — and that was false: the panel showed *this* incident's records
    and offered no route to the rest. The panel has an *every record →* link
    now, and the justification is true rather than merely written down.
  - **Its own first version was mislabelled.** Every journey started at the
    overview, so "the map, from an incident" was satisfied by the overview's own
    link — the shortest path, not the claimed one. Journeys carry a starting
    point now.

  A third thing turned up on the way: **every incident card on the overview
  linked to `/incidents`**, the list. Clicking the incident you were reading
  about took you to a page listing it again — the commonest path into the
  product, going one step sideways.

  *Verified: `/ → /infrastructure`, `/ → /audit`, `/ → /incidents/INC-2026-0901`
  in one click each; `/incidents/… → /infrastructure` in one and `→ /audit` in
  two; 27/27 layout and reachability checks; the header still one row at 65px.*

- [x] **R53 — A landing page that is not the console.** Needs: nothing.
  **Done when:** someone who has never heard of the project can say what it does
  after reading only `/`, and reaches a real incident in one click. — **met.**
  `/` is now the landing page and the console moved to `/overview`. The headline
  states the claim — *four alerts in four tools are one intrusion; this is the
  thing that says so* — and the primary button opens
  `/incidents/INC-2026-0903`, one click, verified by clicking.

  Four things and it stops: the loop in one line, the before/after of an
  incident, what bounded autonomy actually constrains, and the doors in. **No
  pricing**, as the task required — there are no accounts and no billing, and a
  price invites a question the site cannot answer.

  **The arithmetic is made of the demo's own numbers.** `ROADMAP.md` records
  that MTTR is *not computable* in this deployment — the recorded clock is not
  MTTR's clock — so a measured time-saving claim would have been an invention,
  and an invented number on the front page would undo what the rest of the
  product spends its effort proving. What is said instead is checkable on the
  site: the three scenarios' signals arrive **11, 30 and 90 minutes apart**, and
  the cost is the gap between the first and someone joining it to the fourth.

  **The before/after panel and its link disagreed.** The panel describes the
  beaconing scenario; the link went to whichever incident came back first, which
  is credential stuffing. On the one page whose whole job is that the sentence
  and the destination match, they did not. It now finds the incident it is
  describing, matched on the hypothesis rather than an id — an id is a fixture
  detail and would go stale silently the day the scenarios are renumbered.

  *Verified: 30/30 layout and reachability checks, WCAG AA in both themes, every
  click-through journey intact after the route move, 807 tests.*

- [x] **R54 — How it works.** Needs: **R53**.
  **Done when:** every claim on `/` has a page here that substantiates it, and
  the risk table matches the registry rather than restating it from memory. —
  **met, and both halves were checked rather than assumed.**

  **The risk table is generated, not written.** `dharma.policy_model()` returns
  the bands `_tier_for` branches on and the approvers `evaluate` attaches, and
  `/api/v1/policy/model` serves them. Proved by moving the autonomous ceiling
  from 30 to 25 and watching the model report `0–25` and `26–60` — a page with
  the numbers typed in is what that change would have silently contradicted.
  The same route carries the two gates, because *"this deployment is in dry run
  and its environment is not on the live list"* is a claim, and it is worth
  exactly what a reader's ability to check it is worth.

  `evaluate` now reads the shared `APPROVERS` table rather than its own copy.
  Two answers to "who may approve this" is one too many, and the day they
  disagree the wrong one is the one on the marketing site.

  **The claim audit found two gaps.** A check walked every claim on `/` and
  looked for something backing it here: *maps each step to a known technique*
  had nothing behind it, and *risk from blast radius, confidence and
  reversibility* mentioned only the first. Both are covered now — an ATT&CK
  section listing the three techniques of one real incident, in order, and the
  risk inputs named. Nine claims, nine substantiations.

  Reached from the landing page beside the claims it backs, and from the footer
  so it is available everywhere — not a seventh navigation tab, because R52's
  rule is that a tab is for what a visitor *arrives* looking for, and this is
  what they look for *after* reading a claim.

  **A regression surfaced on the way, from data rather than code.** URLhaus
  ingested a 56-character random subdomain, and `/observatory` — laid out
  against IP addresses — went 100px wide at 375px. Feeds bring whatever the
  internet contains, so the identifier wraps now. `min-w-0` as well as
  `break-all`: a flex item refuses to shrink below its content's minimum
  contribution, so breaking alone would not have been enough.

  *Verified: 33/33 layout and reachability checks, WCAG AA in both themes,
  807 tests.*

- [x] **R55 — Deploy Phase 5 and review.** Needs: **R51, R52, R53, R54**.
  Deployed and reviewed. **Phase 5 is closed — R50–R55 all done.**

  *Evidence, against `https://pashupatastra.vercel.app`: 33/33 layout and
  reachability checks at 375, 768 and 1280; WCAG AA in both themes; every
  click-through journey intact; all four chat starters grounded with citations
  resolving; all three blue team scenarios playable and discriminating; 939
  tests; ruff clean.*

  **The phase set out to fix one thing and did.** A stranger opening the URL
  used to land in an operator's console. They now land on a page that states
  the claim — *four alerts in four tools are one intrusion* — and reaches a real
  incident in one click. At 375px the claim, the explanation and the button are
  all above the fold, which is the whole of the thirty seconds this phase was
  written about.

  **What the pass found**, beyond the checks:

  - **The not-found page still said "Back to overview"** and pointed at `/`,
    which stopped being the Overview when R53 moved the console. A small lie, on
    the page a reader reaches when something has already gone wrong.
  - **Nav highlighting was worth re-checking rather than assuming.** R52
    replaced `isCurrent`'s exact-match branch with a bare prefix, and
    `/observatory` sitting beside `/overview` is exactly the pair that would
    have collided. Verified on all eight routes, including that `/` and
    `/how-it-works` correctly highlight nothing.
  - **The CISA feed looked stuck and was not.** Its cursor sat at 2026-08-21
    while URLhaus had moved to the 24th. Fetching the catalogue settled it:
    CISA has published nothing newer, and the cursor matches its latest entry
    exactly. This is the R25 decision earning its keep — a feed that has stopped
    and a feed that is quiet look identical until you publish the cursor.

  **Three days of real operation.** The hourly schedule has been ingesting since
  R24 without intervention; the URLhaus cursor has advanced to today. Nothing in
  the phase needed a manual poke to keep working.

  **Carried forward, unchanged and stated again rather than quietly dropped:**
  every entity still reports `estimated_users: 0`, so blast radius gives real
  entity counts and an absent user figure — absent rather than wrong, because
  inventing one is what R50 forbids. `notFound()` still returns 200 rather than
  404, since the layout streams before the page resolves; readers see the right
  page, crawlers see the wrong status. And Vercel Hobby remains non-commercial,
  so S11's pricing page — not traffic — is the first real bill.
  **Done when:** the deployed site opens on something a stranger understands,
  the console is still one click away, no route was deleted, and `verifyui.py`
  and `verifycontrast.py` both pass on the new pages.
  **Stop here for review.**

---

## The polish pass, added 24 August 2026

A second prompt arrived after Phase 5's tasks were written: a UI/UX and polish
upgrade covering seven priorities, from a real Observatory bug through to a menu
of further cybersecurity capability. It is folded in here rather than kept as a
separate document, because a second plan is how two plans start disagreeing.

Where it duplicates something already planned, the existing task wins and the
new material is folded into it — **Priority 4 ("How it's built") is R54**, which
was already written and already needs doing. Everything else becomes **Phases
5A–5D**, sequenced the way the prompt itself asks for: credibility and
attribution first, then the visitor's first minute, then the agent, then the
capability menu last and only opportunistically.

**These phases run before Phases 6–8.** The SaaS work assumes a console someone
already believes; a feed that prints the same IP twelve times is a reason not
to. Phase 6 keeps its `S1` dependency on `R18` and gains one on `R59`.

### Where the seven priorities landed

| Prompt priority | Tasks | Phase |
|---|---|---|
| 1 — Observatory noise | R56 | 5A |
| 2 — About this build | R57 | 5A |
| 3 — Fast onboarding | R58, and R60 for the richer version | 5A / 5B |
| 4 — How it's built | **R54** — already planned, extended below | 5 |
| 5 — Advanced and fun | R60–R66 | 5B |
| 6 — Expand Sati | R68–R73 | 5C |
| 7 — Capability areas | R75–R86, a menu | 5D |

### Two rules that apply to every task below

1. **No dead buttons.** Anything from the capability menu that is not built is
   either absent or marked as roadmap on `/how-it-works` (R54). A demo with
   fewer real features beats one with a nav item that opens an apology.
2. **Nothing new delays real data.** No loading skeleton, no reveal animation,
   and no palette that has to boot before the page beneath it renders. The
   site's whole argument is that what you are looking at is live; a spinner in
   front of it is an odd way to make that case.

The existing visual language is extended, not replaced: the dark palette, the
`▲ ◆ ● ○` severity glyphs, the spacing and type scales from R40–R44. Copy stays
dry — no "seamless", no "supercharge", no adjective that would survive being
deleted.

**R54 gains one requirement** from the new prompt: alongside the seven stages,
the risk tiers and the two dry-run gates, it carries the live-versus-roadmap
table for Phase 5D, and it explains how effective risk is computed — blast
radius, confidence, novelty, reversibility — and why base risk only ever rises.

---

## Phase 5A — Credibility and attribution

Needs **R55**. Two fixes, and they are the two a visitor notices before anything
else on this list: a feed that repeats itself, and a site with no author.
Everything in Phases 5B–5D is worth less until these land.

- [x] **R56 — Observatory: one row per indicator, not one per report.** Needs: **R23**.
  The feed renders raw API rows, so a single IP reported twelve times in three
  hours is twelve near-identical cards, and the page reads as noise generated by
  a script rather than as intelligence. Group by indicator — IP, URL, hash —
  within a rolling window (3h to start, and the window is a named constant, not
  a literal scattered through the component), collapse repeats to
  `reported 8x in the last 3h`, and put the individual timestamps, reporters,
  tags and status behind an expander so nothing is lost. Sort groups by most
  recent activity, and split *still active* from *gone offline* — the data
  already carries that status and currently spends it on nothing.
  **Done when:** no indicator appears at the top level twice, every individual
  report is still reachable in one click, and a test feeds a fixture with a
  known duplicate count and asserts both the group count and the per-group
  report count.
  *This is a bug, not polish, which is why it is first.*
  Done. The live feed had one address reported **43 times** — 200 reports across
  108 indicators. Grouped in `app/feeds/grouping.py` (server side, so the page
  is not sent 200 rows to render 108) with `GROUPING_WINDOW` as the named
  constant; `/intel` now returns `groups` alongside the raw reports. Verified
  against the deployed site: 60 reports collapse to 34 indicators, 0 duplicate
  identifiers at the top level, every repeat behind an `all N reports` expander,
  and the 24 active / 10 offline split on the page matches the API's own count
  exactly. 11 tests in `testgrouping.py` over a 12-report fixture assert the
  group count, the per-group report count, and that no report id is lost between
  input and output.
  Two decisions worth recording: `active` follows the **latest** report's status
  rather than "some report said online", because carrying the optimistic reading
  forward leaves dead infrastructure on the board as a live threat; and the
  window is rolling relative to *each indicator's own newest report*, not to the
  wall clock, or the count a page prints becomes a function of when it loaded.
  The offline half sits in one collapsed panel instead of in the day timeline —
  a day-by-day chronology of infrastructure that is already gone is a list of
  things that stopped mattering.

- [x] **R57 — Build info, not a bio.** Needs: nothing.
  The site has no author and no repository link, which for a portfolio project
  is the one omission that costs it everything. A footer panel, styled as a
  system readout — version, deploy target, stack — rather than an About Me card:
  builder, one line on why this exists, the GitHub repository, a
  LinkedIn/portfolio link, and the stack **read from `package.json` and the
  Python requirements**, not typed from memory. A stack list claiming a
  dependency the repo does not have is the same failure as an invented metric,
  on the one panel whose whole subject is honesty.
  **Done when:** every framework named is in a manifest in this repo, the panel
  renders on every page, and it reads as another data panel — no photograph, no
  first person, no "passionate about".
  Done, but **not in the shape this task describes**, and the task was wrong
  rather than the implementation.
  Built as specified first: a footer panel on every page carrying the revision,
  the deploy target, and the full stack with version ranges and the manifest
  path each dependency was read from. Rejected on sight — *"it looks like it is
  showing the stuff I am doing while building the website"* — and correctly. A
  bill of materials under every page is the build describing its own working
  conditions to somebody who came to read about an incident, and
  `pytest · ruff · mypy` is of interest to exactly one person, who already knows.
  What shipped instead splits the two things the task had conflated. The
  **attribution** is one line in the footer on every page — builder, source,
  LinkedIn — because a site with no author is the omission that costs a
  portfolio project everything, and that is one line's worth of fix. The
  **stack** moved to `/how-it-works`, names only, no versions and no manifest
  paths, because it is context for a reader who opened that page on purpose.
  Splitting them fixed it; shrinking the panel would not have.
  The honesty constraint survived the redesign intact, which was the part worth
  keeping: `scripts/buildinfo.py` reads `package.json` and the three
  `pyproject.toml` files and **exits non-zero if asked to name a dependency no
  manifest carries**. `testbuildinfo.py` (9 tests) re-parses the manifests itself
  rather than asking the generator what it found, and all four failure modes
  were watched going red before being trusted green: a stale version, an
  invented dependency, a name typed into the component instead of generated, and
  a bio phrase creeping into the attribution.
  Two defects the deployed checks caught that reading the code would not have:
  the panel linked its commit sha to GitHub while the branch was unpushed, so
  the one panel about verifiability shipped a 404 — the sha is now plain text
  unless `VERCEL_GIT_COMMIT_SHA` proves the commit is on the remote; and the
  footer separator glyph measured 1.6:1 and was deleted rather than recoloured,
  since a divider nobody can see is not a divider.
  Verified on the deployed site by `scripts/verifybuild.py`: attribution on 9/9
  pages, 14/14 dependencies rendered and each resolved against a manifest the
  checker parsed itself, the stack asserted *absent* from the other eight pages,
  and every external link fetched. Contrast passes AA in both themes; 33/33
  responsive combinations pass; 959 tests pass.

- [x] **R58 — Start here.** Needs: **R53**.
  A skimmer on `/` currently has to notice a text link to find the real
  incident. A *Start here* affordance near the top, leading straight into it —
  a link or a scroll, **not a modal**, and nothing that blocks the page beneath
  it. The palette in R60 is the richer version of this; this task is the one
  that works without JavaScript.
  **Done when:** a visitor who reads nothing but the first screen reaches a real
  incident in one click, and the affordance is keyboard-reachable and legible in
  both themes.
  Done — and the geometry half was **already true** before the task started, at
  every viewport. Measuring it first is what found the real defect, which the
  task had not anticipated: the button said `Open a real incident →` and pointed
  at a scripted scenario. That was the site's own honesty rule broken on its
  first screen, and R88 made it worse the same day by putting genuinely real
  attacks on `/observatory` — two things called real and only one of them was.
  So the affordance is now a labelled *Start here* with three plain links and a
  line saying which is which: the worked incident is a written scenario that
  exists to show the whole chain, and the Observatory is real. No modal, no
  overlay, nothing that boots before the page under it renders.
  `scripts/verifystart.py` measures the claim as geometry rather than as a
  class name — the link's bounding box must lie fully inside the viewport before
  any scroll — across 6 viewports × 2 themes, and reaches the primary link by
  pressing Tab rather than trusting that a class called `focusable` focuses
  anything. 12/12 pass, contrast passes AA in both themes, 33/33 responsive
  combinations pass.

- [x] **R59 — Deploy Phase 5A and review.** Needs: **R56, R57, R58**.
  **Done when:** the deployed Observatory shows grouped indicators against the
  live feed rather than a fixture, the build panel names the real stack, and
  `verifyui.py` and `verifycontrast.py` pass on both.
  **Stop here for review.**
  Done. All three criteria hold on the deployed site: `/intel/status` shows live
  cursors for all six feeds dated today, the build panel resolves 14/14
  dependencies against manifests the checker parses itself, and both scripts
  pass — 33/33 responsive combinations and every contrast pairing at AA in both
  themes. 985 tests pass.
  Treating this as a review rather than as two script runs is what made it worth
  doing. `scripts/verifysite.py` was written for it: it crawls every internal
  link from the entry page — 58 pages — and checks three things a status code
  cannot, because **`notFound()` under dynamic rendering returns HTTP 200 with
  the not-found body**. A broken link is therefore indistinguishable from a
  working one to anything that only reads status, which is how the bug below
  survived every check so far.
  It found one: `Evidence` in `ui.tsx` linked every citation to `/evidence/`,
  which is correct only for event ids. A hypothesis cites the incident it
  belongs to, so `/evidence/INC-2026-0901` was reachable from every hypothesis
  on the site and rendered "no such page".
  The fix already existed. `chat.tsx` had `hrefFor()` routing refs by kind, and
  **its docstring described this exact bug in `Evidence`** — written, understood,
  and never back-ported. It now lives in `lib/refs.ts` and both use it, so there
  is one answer to "where does a citation go" rather than one per component.
  The detector was proven rather than trusted: it catches `no such page` at
  HTTP 200 on the old URL and passes `/evidence/SEC-0001-a` and
  `/incidents/INC-2026-0901` clean.
  Still open and confirmed here with evidence: `notFound()` returns 200 on
  dynamic routes while a genuinely unknown static path returns a real 404.

---

## Phase 5B — Satisfying to operate

Needs **R59**. The prompt's word is "fun", and its own constraint is the right
one: *fun means satisfying to operate, not decorative.* Nothing here adds
illustration, bright colour or a gradient. Each task either makes the site
faster to use or makes visible a claim it already makes.

Take these in order of leverage and stop when the time budget does — R60 and
R65 are the two that change how the product feels; the rest are additive.

- [x] **R60 — Command palette.** Needs: **R58**.
  `Cmd-K` / `Ctrl-K`, fuzzy across incidents, entities, advisories, actions and
  pages, plus the four named jump points: show me a real incident, let me work
  one myself, show today's threat feed, talk to the assistant. Search runs
  against data already loaded or already cached; a palette that waits on a round
  trip is slower than the nav it replaces.
  **Done when:** it opens from any page, is fully keyboard-operable including
  escape and arrow keys, traps focus while open and returns it on close, and
  degrades on touch to a visible search affordance rather than a shortcut nobody
  can type.
  Done. `components/palette.tsx`, `Ctrl-K` / `Cmd-K`, 87 indexed rows on the
  deployed site — 3 incidents, 11 entities, 33 actions, 40 advisories — plus the
  four named jumps and eight pages.
  **No keystroke waits on a request.** The index is fetched once on the server
  in the layout and handed down as a prop, so filtering is an array scan. A
  palette that round-trips per keystroke is slower than the navigation it
  replaces, which would make it a worse version of the thing it exists to beat.
  `scripts/verifypalette.py` asserts this by counting network requests while
  typing, rather than by reading the code and believing it: **0**.
  The matcher is twenty lines rather than a dependency — it ranks consecutive
  characters and word boundaries, which is what makes `ws` return `ws-0148`
  first. A fuzzy-search library shipped to every visitor to rank 87 short
  strings would be weight for nothing.
  One bug caught before it shipped, and only because the index was checked on
  the deployed site rather than locally: it read `STORE.incidents`, the
  in-memory dict, which is **empty on a durable deployment** where incidents
  live in DynamoDB. Every incident appeared on a laptop and none in production.
  Now `STORE.all()`, with a test asserting the indexed set equals the listed set.
  Verified in a real browser, every clause pressing real keys: opens and closes
  on 7/7 pages, focus captured on open and **returned to the element that had
  it**, six Tabs stayed inside the dialog, arrows move and return, Enter
  navigates and the dialog closes, and a visible search affordance survives at
  390px with touch emulation. 33/33 responsive, AA contrast in both themes, 58
  pages crawl clean, 987 tests pass.

- [x] **R61 — Show that it is live.** Needs: **R56**.
  Observatory and the incident feed poll real sources hourly and the page says
  nothing about it. `last synced 14m ago`, and new entries arriving with a brief
  highlight as they land — **the entry renders first and is highlighted after**,
  never the reverse.
  **Done when:** the sync age is derived from the record's own timestamp rather
  than from page load, and a stale feed reads as stale instead of as empty.
  Done. `128 indicators · 200 reports · last synced 11m ago` in the panel head,
  and each feed carrying `answered 11m ago` under it.
  The task needed a fact the system was not recording. `set_feed_cursor` fires
  only when something new is *stored*, so a healthy feed that answered and had
  nothing to report never updated its timestamp and looked identical to one that
  had stopped answering — and "quiet" versus "broken" is the entire question a
  reader has about a live feed. A sync heartbeat is now written on **every**
  poll, storing or not, and `/intel/status` keeps three facts apart: when a feed
  last answered, where it last moved to, and whether the first is too long ago.
  Never-polled is deliberately **not** stale. A deployment that has not run its
  first ingest is not broken, and colouring it as a fault would cry wolf on
  every fresh start — which is how a reader learns to ignore the warning that
  matters.
  The highlight is added **after paint** by `components/fresh.tsx` rather than
  rendered into the markup, which is what the task asks for and not a detail: a
  class baked into the HTML arrives *with* the row, so a first-ever load would
  flash every entry as new and a feed that had not moved in a day would look
  like it had just landed. The watermark is per-tab `sessionStorage`, wrapped in
  try/catch because a private window throws on access rather than returning null.
  `prefers-reduced-motion` keeps the rail and drops the fade — the information
  is not the animation.
  Verified by `scripts/verifylive.py`, and the age check is the one that matters:
  it loads the page, **waits 70 seconds, loads it again**, and asserts the
  printed age grew. A page deriving freshness from its own render prints the
  same "just now" both times, and no single-load assertion can tell the two
  apart. Observed 600s → 660s.
  The stale check was initially written as a browser route interception and
  reported a failure that meant nothing — **this page renders on the server**, so
  that request never passes through the browser. Split instead: the computation
  is covered by four tests in `testfeeds.py`, and the render was proven once by
  building the site against a local stub reporting every feed stale, which
  printed `last answered … over 3h ago`. What the script keeps is the contract
  the branch depends on — six feeds, six freshness fields each — since a
  silently dropped field would make every feed render as healthy.
  33/33 responsive, AA contrast in both themes, 58 pages crawl clean, palette
  still passes, 991 tests.

- [x] **R62 — The causal chain builds itself.** Needs: **R43**.
  On an incident page, the chain reveals signal → signal → signal → diagnosis
  rather than appearing complete. This is the site's central claim — *this is
  what connecting the dots looks like* — animated once, briefly, and not again
  on that page.
  **Done when:** the full chain is present in the DOM from the first paint with
  motion applied on top, `prefers-reduced-motion` renders it complete and
  instant, and no text is unreadable at any point in the sequence.
  Done. The third clause decided the design: **nothing animates on text at
  all.** A fade-in leaves words at an opacity nobody can read, and half a second
  of that on every incident page is a console being decorative during an
  incident. What moves is the rail drawing downward and each marker lighting as
  the line reaches it, with every word at full contrast from the first frame.
  Additive throughout. `components/chainreveal.tsx` adds one class after mount;
  without it — no JavaScript, a thrown effect, reduced motion — every property
  is already at the value the animation ends on and the chain is simply
  complete. The reveal can never be the path by which the page becomes
  finished. Once per incident per session, so returning from an entity page does
  not replay it.
  **A screenshot found a bug three green checks had missed.** The CSS matched
  the rail and the marker *by position*, and the final step renders no rail — so
  on that one row the marker was `:first-child` and got handed the rail's
  `scaleY(0)`, disappearing for the length of its own delay. Positional
  selectors describe where an element sits; `data-rail` and `data-node` describe
  what it is, and only the second survives a conditional sibling.
  The checks missed it because they measured opacity, and a transform hides an
  element without changing a single colour. `verifychain.py` now samples
  *geometry* on every frame, and that was proven rather than assumed: with the
  old selector re-injected, marker 3 collapses to **24×0** and the check fires on
  exactly that marker while 1 and 2 stay 24×24.
  Two checker bugs fixed on the way, both of the same family — a check that
  reports a defect it invented. It relied on `browser.new_page()` for isolation,
  so the "did it animate" pass inherited the session watermark and reported that
  the reveal never ran; and it sampled from `domcontentloaded`, reading every
  box as 0×0 and calling the whole chain hidden, because it was measuring a page
  that had not been drawn yet.
  Also fixed here: R88's new fact rows overflowed `/observatory` by 47px at
  375px — HIBP's `exposed` is a comma list of data classes, and a flex item will
  not shrink below its content without `min-w-0`.
  33/33 responsive, AA contrast in both themes, 58 pages crawl clean, 992 tests.

- [x] **R63 — Blast radius as a graph.** Needs: **R51**.
  R51 put the access map on the incident page; this gives blast radius its own
  radial view of affected entities beside the list, so *what this reached* is a
  shape rather than a count. Same rule as R50: **no edge without a citation.**
  **Done when:** it draws only edges the incident's evidence establishes, the
  list remains for screen readers, and it collapses to the list on narrow
  viewports rather than overflowing.
  Done. `/topology/blast-radius/{key}` now returns the same reach as a **walk**:
  nodes with a hop depth, and the edges traversed to reach them.
  R50's rule is enforced in the walk, not in the drawing. The traversal
  **refuses to cross an edge carrying no evidence**, so a line on the diagram
  cannot exist without event ids behind it. Filtering at render time would have
  left the node reachable and the reason invisible, which is how a picture ends
  up asserting a relationship nobody can check — and the fixture in
  `testblastradius.py` includes an uncited shortcut to a genuinely affected
  entity, so a walk that ignored citations would find it and draw it.
  `affected` stays authoritative and separate: it is what risk scoring uses,
  the walk only illustrates it, and `uncited` carries the difference rather than
  hiding it. On the live data that difference is currently zero — every reach is
  fully cited.
  Layout is deterministic from the data rather than a force simulation. A
  simulation settles differently on every render, so two people would be
  describing different pictures of the same incident, and it would have to run
  before the page could draw — which Phase 5 forbids.
  Those tests are in their own module because `testgraph.py` is skipped whole
  when Postgres is unreachable. Nothing here needs a database, and a test that
  silently does not run is worse than one that does not exist.
  **Three bugs found, all on pages nothing had been sweeping.** `verifyui` did
  not include an incident detail page until this task added one — the page
  rendering the most data was the page no width sweep visited. It was carrying
  46px of horizontal overflow at 375px, traced by bisection to the audit trail:
  the summary column shares a row with a fixed 64px timestamp, a badge and an
  actor, and on a phone there is no useful width left for it. It now takes its
  own line below `sm`. The access map above it had `overflow-x-auto` on a box
  with no width limit, which scrolls nothing.
  And **seven `<details>` nested inside `<span>`** — flow content inside
  phrasing content, which the parser relocates during hydration and React
  reports as #418, on every incident page and on `/audit`.
  The last one was mine: React 19 treats `<title>` as document metadata and
  hoists it, so a `<title>` inside each `<line>` — an SVG tooltip — became a
  hydration mismatch. The citation moved to `data-evidence`.
  36/36 responsive combinations, AA contrast in both themes, 58 pages crawl
  clean with no browser errors, 997 tests.

- [x] **R64 — The debrief is the payoff.** Needs: **R27**.
  After a Blue Team scenario, a score breakdown across diagnosis, response and
  investigation, naming the specific evidence the player opened and the specific
  evidence they did not. The training value is entirely here and the current
  screen spends it on a number.
  **Done when:** every point gained or lost traces to a named piece of evidence
  or a named decision, and the unopened evidence is listed by name.
  Done. Each breakdown line now carries what it was judged against: the two that
  rest on evidence cite refs (`rests on: SEC-0003-a, …`, and when the diagnosis
  is wrong, `ruled out by:`), and the one that rests on a decision names it —
  *you chose `read_logs` · the plan called for `isolate_host`, `block_ip`*.
  A number with a sentence beside it is still a number.
  The new panel is the **whole board**, not a highlight reel: every entity in the
  exercise appears in exactly one of *opened* and *not opened*, each with the
  evidence it held, and the ones that carried the observation ruling out the
  decoy are marked decisive. Showing only the decisive miss would let a player
  conclude they had covered everything else, which is the opposite of what a
  debrief is for.
  Tested in `testdebrief.py`, on a hand-built incident and a stub graph.
  `testgame.py` skips its entire file when the demo scenarios are not seeded —
  *"demo scenarios are not seeded in this configuration"* — so R64's rule would
  otherwise have been checked only in configurations nobody runs locally. That is
  the third suite in this repository gated behind something usually missing, and
  a test that silently does not run reports green.
  The sharpest test is `test_being_right_by_luck_is_distinguishable_from_being_right`:
  the same correct diagnosis, scored differently depending on whether the player
  opened the thing that rules out the alternative. That distinction is the entire
  reason the investigation category exists.
  Verified against the deployed site by `scripts/verifydebrief.py`, which builds
  the board from the **briefing's own** entity list rather than from anything it
  believes about the scenario — an earlier checker here decided the right answer
  and then graded the site on it, which measured the checker. It opens exactly
  one entity so there is always something to miss, and requires opened ∪ missed
  to equal the board with no overlap.
  Its own browser check was wrong at first in a way worth recording: panel titles
  are uppercased by CSS and `inner_text` returns *rendered* text, so a lowercase
  substring search matched nothing and the "not shown before an attempt"
  assertion passed while measuring nothing — the same mistake `verifybuild.py`
  made in R57. It now reads headings and compares case-insensitively, and
  requires the panel to **appear after an attempt**, without which the first half
  proves only that a panel nobody renders is not rendered.
  36/36 responsive, AA contrast in both themes, 1004 tests.

- [x] **R65 — Approving something should feel like a decision.** Needs: **R20**.
  A proposed action awaiting approval currently reads as a form submit. Give the
  risk score visual weight through the existing `● ◆ ▲` tiers, and a *why this
  tier* explanation drawn from the registry's own factors — blast radius,
  confidence, novelty, reversibility — rather than a restatement of the score.
  **Done when:** the explanation is generated from the same numbers the tier is
  computed from, so it cannot disagree with it, and the tier is distinguishable
  without colour.
  Done. The verdict now carries `tier_reasons` — one record per rule that fired
  while the tier was being decided, emitted by the branch that fired it.
  **The explanation is written by the engine, not the dashboard.** "Generated
  from the same numbers" cannot be achieved by handing the panel the numbers and
  trusting it to reach the same conclusion; that is a second implementation of
  the policy, and the day the two disagree the wrong one is the one an operator
  is reading while deciding. So `evaluate` moves the tier only through a small
  ladder object that records each move, which makes changing the tier without
  saying why something the code cannot express.
  The case that justifies the whole task is a tier the arithmetic does not
  account for: `force_password_reset` scores 20 — squarely autonomous — and is
  denied, because it cannot be undone. The old panel showed 20 and a red badge,
  which reads as a bug in the arithmetic. It now shows *autonomous → never
  autonomous*, and the reason.
  A rule that fires without moving the tier is recorded as **held**, not
  dropped. `delete_infrastructure` is already denied by its score when the
  irreversibility rule reaches it; listing only movements would explain that
  denial as a high number when the real reason is that there is no way back.
  The tier is drawn as the four-step autonomy scale rather than named, marking
  both where the action landed and where its score alone would have put it — the
  gap is the point. The scale's order and bands come from `/policy/model`, for
  the same reason R54 does. It is legible with colour removed: `▲` is shared by
  senior and denied, so position, name, marker and border weight carry it, and
  `verifyapproval.py` measures that through a grayscale filter rather than by
  reading class names.
  Two AA failures found by measuring: `--faint` on the marked cell's tinted
  background lands at 4.25:1. The range text lifts to `--muted` in that cell.
  `scripts/verifyapproval.py` compares the panel against a verdict it obtains
  from the API itself, over a matrix of contexts that reaches every tier by every
  route — the demo incidents alone never produce a tier the score cannot explain,
  so a checker that only looked at them would report green on a panel that had
  never had to explain anything. Negative-controlled: paraphrasing one step and
  thinning the marked border both fail it.
  36/36 responsive, AA contrast in both themes, 1032 tests passing.

- [ ] **R66 — Keyboard triage.** Needs: **R60**.
  `j`/`k` between incidents, `Enter` to open, `?` for the shortcut list. Matches
  the identity the rest of the site already claims.
  **Done when:** shortcuts do not fire while a text input has focus, every one
  of them has a mouse equivalent, and the list is discoverable without reading
  the source.

- [ ] **R67 — Deploy Phase 5B and review.** Needs: **R60–R66**.
  **Done when:** the palette, the chain reveal and the blast-radius graph each
  work on a phone or are absent there by design rather than by accident, and
  `verifyui.py` passes at every breakpoint it checks.
  **Stop here for review.**

  *Deliberately not planned: an easter egg. The prompt offers one and says to
  skip it if it risks the tone. It does — the site's whole register is "this is
  not a toy", and a Konami code is the shortest available argument that it is.*

---

## Phase 5C — Sati, deeper

Needs **R59** and **R21**. Sequenced ahead of Phase 5D because a smarter agent
raises the ceiling on everything else here, and because `/ask` answering cited
questions about one incident is the smallest version of what the homepage
claims.

Every task in this phase is bound by the two rules the rest of the platform is:
**rule 1** — nothing the agent states is true because the model said it — and
**rule 2** — nothing it drafts is adopted without passing through Dharma and a
human. Generation is a new output, not a new authority.

- [ ] **R68 — The reasoning trace is visible.** Needs: **R21**.
  Show the intermediate steps, not only the answer: which evidence was pulled,
  which hypotheses were considered, which were ruled out and on what. The
  homepage asserts that *diagnoses are challenged by evidence*; this is the
  screen that demonstrates it rather than repeating it.
  **Done when:** every step names the records it read, a rejected hypothesis
  names what rejected it, and the trace is stored with the answer so it can be
  audited later rather than regenerated differently.
  *Highest-leverage task in this phase — it turns a claim into a screen.*

- [ ] **R69 — Reasoning across incidents.** Needs: **R68**.
  "Are 0901 and 0902 related?", "same actor pattern?" — answered from entity
  overlap, timing and shared indicators, all of which are already stored.
  **Done when:** a relation is asserted only where the overlap is real and
  cited, *no relation found* is an answer it is willing to give, and a test
  covers a pair with no overlap.

- [ ] **R70 — Drafts, not decisions.** Needs: **R68**.
  A draft playbook and a draft post-incident report, written from an incident's
  evidence. Text output, human review, and the same approval path before
  anything is adopted.
  **Done when:** every assertion in a draft carries its evidence reference, the
  draft is labelled a draft everywhere it appears, and adopting one is an action
  that goes through Dharma like any other.

- [ ] **R71 — Natural language to a detection rule.** Needs: **R70**.
  *"Write a Sigma rule that would have caught the SMB lateral movement in
  0903"* — the agent drafts it, states which telemetry field maps to which rule
  field, and flags what it is unsure of. An LLM generating something, held to
  the same citation discipline as everything else.
  **Done when:** the output parses as valid Sigma, each mapping names the source
  field it came from, and uncertainty is stated in the output rather than
  smoothed away.

- [ ] **R72 — Counterfactuals.** Needs: **R68**.
  *"What if we had blocked the ASN at 09:14 instead of 10:31?"* — reasoned over
  the causal chain timeline already stored per incident, estimating the blast
  radius that would not have happened. Ties to the *cost of the gap* framing R53
  put on the homepage.
  **Done when:** the estimate is derived from stored timeline and graph records,
  is presented as an estimate with its basis stated, and refuses rather than
  guesses where the timeline does not support the question.

- [ ] **R73 — Argue the other side.** Needs: **R68**.
  Before finalising a diagnosis, a second pass arguing the alternative
  explanation and then saying why it was rejected — surfaced as *the
  plausible-and-wrong explanation*, which is language the Blue Team rubric
  already uses. The rubric becomes demonstrable by the agent scored against it.
  **Done when:** the alternative is a real competing hypothesis rather than a
  restatement, the rejection cites evidence, and a case where the alternative
  *wins* is possible and is tested.

- [ ] **R74 — Deploy Phase 5C and review.** Needs: **R68–R73**.
  **Done when:** every new output is cited, no generated artefact can be adopted
  without an approval record, and the Groq token ceiling from R19 still holds
  with the trace and the self-critique pass both running.
  **Stop here for review.**

---

## Phase 5D — The capability menu

Needs **R74**. **This phase is a menu, not a checklist.** The prompt is explicit
and it is right: pick the subset the data model and the time budget actually
support, and mark the rest as roadmap on R54's page. Ticking things here is
worth less than being accurate about which are ticked.

Nothing here starts before Phases 5A–5C are done, and anything needing accounts
or per-user persistence belongs to Phase 6, not to this one.

**Detection and threat intelligence**

- [ ] **R75 — The ATT&CK matrix as a view.** Needs: **R17**.
  A tactic/technique matrix across the whole incident library rather than tags
  on one incident. Coverage is the interesting claim; a tag is not.
  **Done when:** every filled cell links to the incidents that fill it, and
  empty cells read as *not observed* rather than as *not covered*.

- [ ] **R76 — More real feeds.** Needs: **R23**.
  Beyond CISA KEV and URLhaus: NVD/CVE recent disclosures and AlienVault OTX
  pulses, both free and both polled the way the existing feeds are.
  **Done when:** each new feed has its own poller, its own failure handling and
  a source attribution on every record it produces — and one feed being down
  does not empty the page.

- [ ] **R77 — A browsable detections library.** Needs: **R71**.
  The rules from R71, plus any written by hand, as a page tied back to the
  incidents they came from.
  **Done when:** every rule names its incident and its author — drafted by the
  agent or written by a human — and the two are visually distinguishable.

- [ ] **R78 — Indicator enrichment in place.** Needs: **R76**.
  Any IP, hash or domain anywhere in the app is clickable, and queries the
  intelligence already held before it queries anything external.
  **Done when:** lookups are cached, a miss reads as *nothing known* rather than
  as an error, and no lookup blocks the page it was triggered from.

**Response and operations**

- [ ] **R79 — Playbooks over the action registry.** Needs: **R20**.
  Named, reusable chains of existing actions — `revoke_session`, `isolate_host`
  — with an aggregate risk score and approval routing derived from the steps.
  **Done when:** a playbook's tier is computed from its steps and is never lower
  than its highest step, and a playbook cannot execute a step whose own approval
  would have been refused. *Rule 2 has no chained-action exemption.*

- [ ] **R80 — The post-incident report as an export.** Needs: **R70**.
  Timeline, root cause and recommended follow-ups, as Markdown and PDF.
  **Done when:** an exported report carries its evidence references and the
  audit record ids, so it is checkable away from the site that produced it.

- [ ] **R81 — Framework mapping.** Needs: **R75**.
  Incidents and actions tagged against NIST CSF or ISO 27001 control families —
  a real enterprise ask, and cheap once the ATT&CK mapping exists.
  **Done when:** each mapping is stated as an assertion with its basis, not as a
  certification, and the page says which it is.

**Simulation and training**

- [ ] **R82 — Adversary emulation.** Needs: **R26**.
  Generate a synthetic incident on demand from a TTP chain or an actor profile,
  instead of three fixed scenarios. The largest single increase in replay value
  available here.
  **Done when:** generated incidents are labelled synthetic everywhere they
  appear, carry the same evidence structure as the fixed three, and never enter
  the same feed as real advisory data.

- [ ] **R83 — Phishing simulation.** Needs: **R26**.
  A mock inbox, scored by the same rubric as Blue Team.
  **Done when:** it shares R64's scoring code rather than reimplementing it.

- [ ] **R84 — Leaderboards and streaks.** Needs: **S2**.
  **Deliberately dependent on Phase 6, not on this one.** Per-user history needs
  accounts and persistence; building it before S2 means inventing half an
  identity that S2 then has to unpick.
  **Done when:** it is built on Cognito sessions and per-tenant storage — or not
  built.

**Visibility and analytics**

- [ ] **R85 — Topology as its own screen.** Needs: **R50**.
  Mostly delivered already: R50 built the graph and R51 put it on the incident
  page. What remains is the estate-level view of watched entities and observed
  access paths as a first-class screen rather than a delisted route.
  **Done when:** it shows the whole estate under the same citation rule, and the
  10 observed access paths on the overview link into it.

- [ ] **R86 — Baseline and deviation.** Needs: **R17**.
  Normal versus current for the entities already tracked. Threshold-based is
  fine and honest; **the framing is the value, and calling a threshold "ML" is
  the one way to lose it.**
  **Done when:** the method is stated on the page, the baseline window is
  visible, and no deviation is shown without the baseline it deviates from.

- [ ] **R87 — Deploy Phase 5D and review.** Needs: whichever of **R75–R86** were
  chosen.
  **Done when:** `/how-it-works` lists every item in this phase as live or as
  roadmap, that list matches what is actually deployed, and no route exists for
  anything not built.
  **Stop here for review.**

---

## Phase 6 — Tenancy and identity *(the floor a SaaS stands on)*

Needs **R18**, **R55** and **R59**. Everything up to here is one console showing one
organisation's data to anyone who opens the URL. A SaaS is the opposite claim:
many organisations, each seeing only its own, and each certain the others cannot
see theirs. That claim is made in the data model, not in the login screen.

**The order in this phase is not negotiable.** Tenancy lands before sign-in, and
scoping lands before invitations. A product that adds accounts first has a
window in which users exist and data is still shared, and nobody finds that
window by using the product — they find it by being in someone else's data.

`packages/core` already carries a `tenant` setting that nothing enforces. That
is the seam this phase makes real.

- [ ] **S1 — A tenant on every record.** Needs: **R18**, **R59**.
  `tenant_id` on incidents, audit records, events, nodes, edges and cached
  answers, and in the DynamoDB partition key beside the namespace — the same
  mechanism that already separates `prod` from `test`, doing the job it was
  shaped for. Backfill the demo data to a `demo` tenant.
  **Done when:** no store method can read or write without a tenant, enforced by
  the signature rather than by convention, and a test proves that two tenants
  writing the same incident id get two incidents.

- [ ] **S2 — Sign-in.** Needs: **S1**.
  **AWS Cognito** — 50,000 monthly active users on the always-free tier, which
  is more than this will ever need and keeps identity on the platform the rest
  of the system already runs on. Hosted UI first; a custom form is a later
  cosmetic task, not a prerequisite.
  **Done when:** a visitor can create an account, sign in, sign out, and reach a
  page that names them.
  **Cost:** free to 50k MAU. Stated because "auth" is where SaaS projects
  usually acquire their first bill.

- [ ] **S3 — Organisations and membership.** Needs: **S2**.
  A user belongs to one or more organisations; an organisation owns tenants.
  Roles: `owner`, `analyst`, `viewer` — three, because two cannot express "may
  approve" and four are invented before anyone has asked for them.
  **Done when:** a new sign-up creates an organisation, and a user's role is
  visible in their session.

- [ ] **S4 — Every route scoped to the caller.** Needs: **S3**.
  **The security task of this phase.** Each API route derives its tenant from
  the authenticated session, never from a parameter — a tenant id in a request
  body is an invitation to type someone else's.
  **Done when:** a test signs in as one organisation, requests another's
  incident by id, and gets a 404 rather than a 403. *404, deliberately: a 403
  confirms the id exists, and confirming which incident ids exist is itself a
  leak.*

- [ ] **S5 — Approval means a person now.** Needs: **S4**.
  Dharma's `required_approvers` are role names; approval is currently an
  anonymous POST. With identity available, an approval records *who*, and the
  route refuses a caller whose role is not in the verdict's approver list.
  **Done when:** a `viewer` cannot approve a `senior` action, the audit record
  names the human who did, and the existing approval-fatigue metrics attribute
  to real people. Closes the gap R20 left: the agent's proposals reach a queue
  that, until now, anyone could clear.

- [ ] **S6 — Invite a teammate.** Needs: **S3**.
  Email invitation with a signed, expiring link. **SES** in sandbox mode is free
  and sends only to verified addresses, which is enough to build and test
  against; leaving the sandbox is a support ticket, not a code change.
  **Done when:** an invited address can join an existing organisation and lands
  in it, not in a new one of their own.

---

## Phase 7 — The product surface *(what someone can buy)*

Needs **S4**. The console is the thing being sold, but nobody buys a console
they cannot get into, and nobody signs up for something that opens on a
dependency map. This phase is the shell around the product.

- [ ] **S7 — The console moves to `/app`.** Needs: **S4**, **R53**.
  `/` becomes the landing page built in R53; the console lives under `/app` and
  requires a session. Marketing pages stay static and public — they are what a
  search engine and a stranger see.
  **Done when:** signed out, `/app/*` redirects to sign-in and `/` renders
  without touching the API; signed in, `/app` is the console.

- [ ] **S8 — Onboarding that ends in something real.** Needs: **S7**.
  Create an organisation, connect a source, see a first incident. The demo
  scenarios are the fallback so a new tenant is never an empty console — but
  they are **labelled as sample data**, everywhere they appear. An empty state
  that quietly fills itself with fiction is how a product teaches its users not
  to trust it.
  **Done when:** a new sign-up reaches a populated console in under two minutes
  without reading anything.

- [ ] **S9 — Settings, and an API key.** Needs: **S7**.
  Organisation name, members, roles, and per-tenant API keys for the ingest
  route — hashed at rest, shown once at creation.
  **Done when:** a key can be created, used against `/ingest`, and revoked, and
  a revoked key is refused.

- [ ] **S10 — Plans, and limits that are real.** Needs: **S9**.
  A `free` plan with quotas the code actually enforces — entities watched,
  incidents retained, agent questions per day. Enforced at the seam, returning
  402 with what was exceeded and what the limit is.
  **Done when:** exceeding a quota is refused with a message naming the number,
  and `/health` reports current usage against it. *The chat quota already half
  exists as `chat_token_ceiling`; this makes it per tenant.*

- [ ] **S11 — Pricing, and a way to say yes.** Needs: **S10**.
  A pricing page with the plans from S10, and a waitlist form for paid tiers.
  **No payment integration.** Stripe costs nothing to add and everything to
  operate — refunds, tax, dunning, a legal entity — and none of that should be
  built before someone has asked to pay.
  **Done when:** the page states what each plan includes, matching S10's
  enforced numbers rather than a marketing table that drifts from them.

- [ ] **S12 — Terms, privacy, and a security page.** Needs: **S7**.
  Not decoration: this product ingests telemetry from other people's
  infrastructure. The security page states what is stored, where, for how long,
  and what the agent is permitted to do — which is the shortest honest summary
  of `docs/SECURITY.md` and R20.
  **Done when:** all three exist, are linked from the footer, and say something
  specific enough to be wrong if the system changed.

---

## Phase 8 — Operating it as a service

Needs **S10**. The difference between a deployed app and a service is that
somebody is accountable for it while nobody is watching.

- [ ] **S13 — Per-tenant metering.** Needs: **S10**.
  Tokens, ingested events, actions evaluated and storage, per tenant per day.
  The `Accountant` already does this per incident and per agent; this adds the
  dimension a bill or a quota would be argued from.
  **Done when:** a tenant's usage for a day can be produced from stored records,
  not reconstructed from logs.

- [ ] **S14 — Status, and knowing before the user does.** Needs: **S13**.
  A public status page driven by the same `/health` the console reads, plus an
  alert when the API, the store or the model provider stops answering.
  **Done when:** killing the model provider's key turns the status page amber
  within a minute and does not take the console down with it.

- [ ] **S15 — A way to be told something is wrong.** Needs: **S7**.
  A feedback route from inside the console that files with context — tenant,
  page, and the last audit records — so a report arrives with the evidence
  attached rather than as "it broke".
  **Done when:** a report from the console arrives with enough context to
  reproduce it without replying to ask.

- [ ] **S16 — Deploy Phase 6–8 and review.** Needs: **S5, S8, S11, S14**.
  **Stop here for review.**
  **Done when:** two organisations exist, each sees only its own incidents,
  neither can approve the other's actions, quotas are enforced, and the landing
  page is what a stranger reaches first.

---

## Out of scope

From the prompt's own non-goals, repeated because they are the things most
likely to creep in: no multi-tenant SaaS, no billing, no auth beyond what
exists, no fine-tuning or MLOps, no graph database, no SIEM/EDR integrations,
and no describing anything as "autonomous" unless an action actually executed
without a human approving it.

---

## Phase R — real attacks, not scripted ones

**Owner decision, 24 August 2026.** *"i want real time incident and real time
help in cyber space not fake data"*, then *"not my code stuff i want real stuff
like the world cyber attacks and incidents"*. The three scripted scenarios go.
Everything the site presents as an incident becomes something that actually
happened.

This supersedes the parts of Phases 1–5 that assume a scripted corpus. It does
not supersede the engines: Dharma, the action registry, the audit ledger and the
verification loop are unchanged and are the reason this is worth doing at all.

### The distinction the whole phase rests on

Real data arrives in two kinds, and conflating them would reintroduce exactly
the fabrication this phase exists to remove.

**Reported attacks** — ransomware.live victim disclosures, Feodo Tracker's live
C2 servers, ThreatFox IOCs, HIBP breach records, CISA KEV. Real, dated, sourced,
free, and already fetching. What they carry is *that it happened and to whom*.
What they carry nothing about is *how*.

So a reported attack gets **no causal chain and no action plan**. We have no
telemetry for it, and inventing three plausible steps and a `isolate_host`
proposal for somebody else's breach would be the same failure as an invented
metric, dressed as analysis. `Hypothesis.evidence` has `min_length=1` for this
reason and the schema should be left to enforce it.

A group's documented tradecraft may be shown, but as a statement about *the
group* and never about *this intrusion* — "Qilin's published tradecraft includes
T1486" is a sourced claim; "Qilin encrypted this victim's files via T1486" is a
guess with a technique id stapled to it.

**Observed attacks** — a honeypot on infrastructure we own. Real attackers, real
credentials tried, real commands run, and telemetry we actually hold. This is
the only source that legitimately supports the full loop: observation →
hypothesis with evidence → causal chain → plan → Dharma → execute → verify.

The loop is the product. Reported attacks give it real context; observed attacks
give it real work.

### Sequencing, and why the deletion comes last

Deleting the scripted incidents first would leave `/incidents`, `/overview`,
`/blue-team` and `/actions` empty until the honeypot lands. The scripted
scenarios are removed in **R92**, once real ones exist to replace them — not
before.

- [x] **R88 — Connectors for the real feeds.** Needs: **R23**.
  `ransomware.live` (recent victims), Feodo Tracker (live C2), ThreatFox (recent
  IOCs), HIBP (disclosed breaches). All four verified reachable with no API key
  on 24 August 2026. In `packages/connectors/drishti/` beside the existing
  feeds, each returning schema-validated records with the publisher's own
  timestamps and a link back to the source record.
  Rate limits and courtesy: cached, polled on the existing hourly schedule, and
  a `User-Agent` that identifies this project — the URLhaus work already proved
  an anonymous urllib request gets a Cloudflare 1010.
  **Done when:** each connector is tested against a committed sample of the real
  response, a malformed record is dropped rather than crashing the poll, and no
  connector invents a field the source did not send.
  Done. `app/feeds/attacks.py`, 26 tests against samples captured from the live
  endpoints and committed under `tests/samples/` — real shapes, including the
  awkward parts a tidy fixture would have omitted: ransomware.live sends `"N/A"`
  for a missing description, Feodo sends `first_seen_utc: null` on most rows,
  and HIBP's `BreachDate` is routinely years before its `AddedDate`.
  A new `EntityKind.ORGANISATION` was needed. A victim is not an `ASSET` —
  that kind means a resource *this* estate protects, and filing a stranger's
  company there would put it on the topology map and let blast radius traverse
  into it.
  `claim_url` on a ransomware.live record is a **Tor leak site serving stolen
  data**. Nothing links to it; provenance points at ransomware.live's clearnet
  page for the group, and a test asserts no `.onion` string survives anywhere in
  a serialised event.
  Three bugs found by deploying rather than by reading:
  (1) `/intel` imported `FEEDS` from `sources.py` instead of the merged registry,
  so all four feeds polled fine, wrote 44 real events, and were filtered out of
  the only endpoint that reads them — every piece worked and the site showed
  nothing. A test now asserts polled and served are the *same set*, not that one
  contains the other.
  (2) HIBP breaches were dated to `BreachDate`, sorting every one of them off the
  end of a recency timeline; the event being recorded is the **disclosure**, and
  the breach date is a label.
  (3) **R56's active/offline split assumed every feed reports liveness.** It did
  not: `active` was `status == "online"`, so ransomware claims and disclosed
  breaches — which are neither up nor gone — evaluated false and were collapsed
  into a panel headed "Gone offline". Four of the six feeds were live on the site
  and unreachable. `active` is now three-state and absent no longer means dead.
  HIBP had made it worse by using `status` to mean *verified*; that label is now
  `confirmation`.
  Live on the deployed site: `krybit claims a breach of resi.com`, `qilin claims
  a breach of A&E + SMA Design`, `coinbasecartel claims a breach of Westwing
  Group SE`, and QakBot and Emotet controllers answering right now.

- [ ] **R89 — Reported attacks, modelled honestly.** Needs: **R88**.
  A real disclosure becomes a first-class thing on the site carrying victim,
  group, date, sector, country and the source link — and *visibly carrying no
  causal chain*, because none is known. The absence is the honest part and
  should read as deliberate rather than as missing data.
  **Done when:** no reported attack has a hypothesis, causal chain or plan
  attached; every field on screen traces to a field the publisher sent; and a
  test asserts that constructing one from a feed record produces no invented
  technique attribution.

- [ ] **R90 — The honeypot.** Needs: **R88**.
  An SSH/telnet honeypot on the Oracle Always Free VM (`scripts/oracle-ollama.sh`
  already provisions the box). Real attackers arrive within minutes of exposure.
  Isolated from everything else, no real credentials, no path to any other
  system, and it holds nothing worth stealing.
  **Done when:** the box is up, events reach Drishti, and the first real
  intrusion attempt is visible on the site with its source IP, the credentials
  tried and the commands run.

- [ ] **R91 — Real incidents, full loop.** Needs: **R90**.
  Honeypot telemetry correlated into incidents the way the corpus scenarios were
  — hypotheses citing real events, a causal chain built from what was actually
  observed, a plan scored by Dharma. This is the first time every claim on the
  page is about something that happened to infrastructure we own.
  **Done when:** an incident exists whose every citation resolves to a real
  observed event, and Dharma's verdict on its plan is recorded in the audit
  ledger.

- [ ] **R92 — Delete the scripted scenarios.** Needs: **R89, R91**.
  Remove `seed.py`'s corpus replay and the three `INC-2026-090x` incidents.
  Consequences to handle rather than discover: **Blue team mode** scores against
  a known answer and has no known answer for a real incident — it either moves
  to a labelled training corpus kept for that one purpose or it goes; the
  **landing page** before/after walkthrough is written around `INC-2026-0903`;
  and `/actions` currently derives its relevance from the scripted plans.
  **Done when:** no incident on the site is scripted, nothing links to a deleted
  id, and the landing page describes the real thing.

- [ ] **R93 — A read must not write to the audit ledger.** Needs: nothing.
  Found while answering a question about the audit trail on 24 August 2026:
  rendering `/incidents/[id]` POSTs to `/policy/evaluate`, which appends an
  append-only audit record. The page is `force-dynamic`, so **every page view
  writes one**. 143 of 299 records were the identical
  `revoke_session: risk 31 → approval` line — 48% of the ledger was page views.
  Computing a verdict to *display* is not the same act as computing one to
  *authorize*, and rule 6's "audit everything" means decisions, approvals and
  executions, not renders. A non-recording preview serves the page; the
  recording call stays for actual authorization.
  **Done when:** loading an incident page any number of times adds no audit
  records, authorizing an action still records exactly one, and a test asserts
  both by counting the ledger before and after.

---

## Phase Sati — the agentic layer, and getting better with time

**Owner decision, 24 August 2026**, from the *Layers of AI* diagram: *"i want my
ai to [have] all those layers so it can get better with time"*.

The diagram is a taxonomy of the field rather than an architecture, and two of
its rows are already this project's strongest ground: **Classical AI** is Dharma
(symbolic rules, risk tiers), the action registry (an expert system) and the
topology graph with its MITRE mapping (knowledge representation); **Generative
AI** is the gateway. Two more rows — neural networks and deep learning — stay
deliberately empty. Hand-building CNNs, LSTMs or VAEs here would reimplement
what the model provider already does, with no training data, no GPU and a free
tier, and a box added to a diagram is not a capability.

What is left is the row that matters and the phrase that matters. Of the five
**Agentic AI** boxes, Sati has *Tool Use* (four tools, and `AgentSpec.may_use`
makes an undeclared tool unreachable rather than discouraged) and *Autonomous
Execution* (present, and deliberately shut at `risk_limit=0` because the input
arrives from an unauthenticated public text box). It has neither *Planning* nor
*Memory*.

And **"better with time" is the requirement underneath all of it.** An agent
that plans and recalls but never finds out whether it was right does not
improve; it repeats itself with more steps. So the phase ends at learning rather
than at memory, and the engines for it already exist unused: `Smriti` carries
`Outcome`, `Trust`, `MatchBasis` and `score_retrieval`, and `learning.py` and
`arms.py` were written for exactly this.

Order is not negotiable. Memory is worth little without a loop to inform, and
learning is meaningless without an outcome to learn from.

- [x] **R94 — Planning: reach for the tool before giving up.** Needs: **R26**.
  **Corrected after reading the gateway rather than assuming.** The investigate
  loop already exists: `gateway.py` runs `for hop in range(max_hops + 1)` with a
  token budget, a per-hop trace, and `chat_max_tool_hops = 4`; the last hop is
  offered no tools, which is what makes the limit a limit. The mechanism is not
  the gap.
  The gap is that Sati does not use it. Asked *"which hosts did ws-0148 open SMB
  to, and what is the blast radius of the busiest one?"* against the live
  deployment, it answered at **hop 0 with no tool call**: *"I cannot tell from
  what I have… it does not name those hosts."* It was holding `get_entity` and
  `blast_radius`, either of which would have answered.
  Refusing to invent is right and is the rule working. Refusing to *look* is not
  — an agent that declines to answer a question its own tools cover is a search
  box that apologises. What is missing is the step before the refusal: name what
  would settle the question, check whether a tool provides it, and only then
  report that it cannot be answered.
  A bounded loop: propose the next lookup, call the tool, revise, and stop —
  with a hard step ceiling, because an agent that can loop is an agent that can
  loop forever on somebody else's free tier. Every step keeps the existing
  bounds: `AgentSpec` gates the tools, every claim is still checked against what
  was actually retrieved, and a step that retrieves nothing is a reason to stop
  rather than to try again.
  The trace is the product as much as the answer is. R68 asks for the reasoning
  to be visible; this is the thing that produces something worth showing.
  **Done when:** the SMB question above is answered from a tool call rather than
  refused, a question genuinely outside the evidence is *still* refused, the
  existing hop ceiling is proven to hold under a model that keeps asking, and
  every step's tool call and result reach the audit ledger.
  Done, and the fix was four sentences of prompt rather than any code. The old
  rule 1 read "if the evidence does not contain the answer, set answerable to
  false" and never mentioned looking; `lookup_advisory` was the control that
  proved it, being the one tool with a rule pointing at it and the one tool that
  got called. Rule 1 is now *look before you decline*, and `PROMPT_VERSION` is 4.
  **Both failure directions are measured, because they pull opposite ways.**
  Refusing to look is the bug; answering anyway is the over-correction and is
  far worse on a console whose whole argument is that its claims can be checked.
  `scripts/verifyagent.py` therefore carries questions that are genuinely
  unanswerable and requires those to still be refused — a run where everything
  is answered is a regression, and a battery of only answerable questions could
  not tell the difference.
  Measured on the deployed agent. Before: hop 0, **no tool call at all**,
  declined. After: a tool call on every question the tools cover, `app-07`'s
  blast radius and the `sso-portal` reach both answered from lookups, and the
  guard question still declined with no tool call.
  One expectation in the battery was **wrong and was corrected against the
  store, not against the agent**. It demanded an answer to "which hosts did
  ws-0148 open SMB to"; the stored chain says only "two hosts never previously
  contacted", and while two others appear in `affected_entities`, naming them as
  the SMB peers is inference the evidence never states. Asserting it is precisely
  the plausible-and-unverifiable claim this console refuses to make, so the
  agent looking and then declining is correct — the checker was deciding the
  answer, which is the failure this script exists to catch elsewhere.

- [ ] **R95 — Memory: Smriti, wired to the agent.** Needs: **R94**.
  The memory engine exists and the chat agent's own prompt says *"You have no
  memory of other conversations."* Recall is of **incidents and their outcomes**,
  never of users — there are no accounts, and building a per-person history
  without them would be building the wrong thing twice.
  Retrieved memories are evidence like any other: cited, checkable, and subject
  to the same rule that an unverifiable claim is removed. A recollection that
  cannot be traced to a stored record is not a memory, it is the model agreeing
  with itself.
  **Done when:** an answer about a new incident cites a prior one where the
  overlap is real, a test proves a fabricated recollection is stripped, and
  `Trust` is honoured — a low-trust memory cannot outrank retrieved evidence.

- [ ] **R96 — Learning: outcomes close the loop.** Needs: **R95**.
  The part that makes "better with time" true rather than aspirational. An
  answer, a plan and a retrieval each have an outcome that is already observable
  — the verification result, the approval decision, whether the cited evidence
  held. Feed those back so retrieval trust and strategy selection move on
  evidence rather than staying where they were initialised.
  **Improvement must be measured, not asserted.** `score_retrieval` already
  exists to produce a number; a claim that the agent is learning, with no
  before-and-after, is precisely the invented metric this project refuses
  everywhere else.
  **Done when:** a recorded outcome demonstrably changes a later retrieval, the
  change is visible as a score moving between two measured runs, and a bad
  outcome lowers trust rather than only a good one raising it.

- [ ] **R97 — Show the layers that are real.** Needs: **R96**.
  A page mapping what this system actually is onto the taxonomy — Dharma to
  symbolic reasoning, the graph to knowledge representation, the registry to an
  expert system, the loop to the agentic row — **generated from the code**, the
  way `/how-it-works` reads its risk tiers from the engine.
  It must name what is absent as absent. A layers diagram with every box filled
  is a marketing asset; one that says "no neural networks here, and why" is a
  claim a reader can check, which is the only kind this site makes.
  **Done when:** every capability shown resolves to a module in this repository,
  the empty layers are shown as empty with the reason, and nothing on the page
  is written from memory.
