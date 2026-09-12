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

Phase 5E ─ what two reviewers hit        needs R59   ← runs before Phase 6
  R93 ──► R98      R99 ──► R100 ──► R101
  R27 ──► R102     R21 ──► R103     R22 ──► R104     R68 ──► R105
  R93, R98..R105 ─────────────► R106 (deploy + review, carries R74's measurements)

Phase 5F ─ evidence                      needs R106  ← mapped in "O1 visa roadmap.md"
  R99 ──► R107 ──► R109
  R108 (licence decision first)     R111     R112 (domain purchase first)
  R110 ──► (docs/research/STUDY.md)
  R107..R111 ──────────────────► R113 (deploy + review)

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
every `S` dependency written against them for the sake of tidier arithmetic. The review pass of 12 September 2026 continues at `R98` as
Phases **5E–5F**, for the same reason; `R93` is not renumbered, it is moved.

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

- [x] **R66 — Keyboard triage.** Needs: **R60**.
  `j`/`k` between incidents, `Enter` to open, `?` for the shortcut list. Matches
  the identity the rest of the site already claims.
  **Done when:** shortcuts do not fire while a text input has focus, every one
  of them has a mouse equivalent, and the list is discoverable without reading
  the source.
  Done. `components/keys.tsx` holds the one answer to *is somebody typing* —
  `Ctrl-K`, `/`, `?` and `j`/`k` all defer to it, where three of them previously
  each had their own opinion or none. `components/triage.tsx` is the list.
  **The help sheet is a registry, not a written list.** `j`/`k` are bound on the
  incident list and nowhere else, so the sheet is assembled from what the
  mounted page actually registered plus the four globals. A help screen that
  told a reader on the audit page that `j` moves to the next incident would be
  worse than no help screen.
  The globals were already there and undocumented: `/` has focused the search
  field since R15 and `Ctrl-K` since R60, and a shortcut list containing only
  the shortcuts added most recently is a list that teaches the wrong thing.
  Order comes from the page as an explicit index per card, not from the order
  items happen to mount in — React does not promise mount order matches document
  order, and a triage list that walks the page in the wrong order looks like it
  worked.
  Not applied to the overview's compact incident list: every row there is a
  single link that Tab already reaches, so `j`/`k` would duplicate a key that
  already works rather than accelerate anything.
  **Two bugs the browser found and reading would not have.** `useEffect(() =>
  bind(show))` returns `show` as its cleanup, so the first registry change had
  React "clean up" by calling it — the shortcut sheet opened itself on load.
  And the first checker shared one page between probes, so `k` was measured from
  wherever the previous probe had left the cursor.
  `scripts/verifykeys.py` takes the sheet as its **input**: it reads the rendered
  rows and demands each be demonstrated, so a key listed but unbound fails, and
  a key bound but unlisted fails too. A row naming a shortcut the checker has no
  probe for is a failure rather than a skip — that is the drift this guards.
  Negative-controlled: a fake row and a removed typing guard each fail it.
  `verifycontrast.py` gained `--press`, because everything inside a dialog was
  being skipped by every contrast run the site has ever done — "it is not on
  screen by default" is not an exemption. The sheet measures AA in both themes.
  36/36 responsive, 58 pages crawl clean, 1032 tests passing.

- [x] **R67 — Deploy Phase 5B and review.** Needs: **R60–R66**.
  **Done when:** the palette, the chain reveal and the blast-radius graph each
  work on a phone or are absent there by design rather than by accident, and
  `verifyui.py` passes at every breakpoint it checks.
  **Stop here for review.**
  Deployed. Lambda carries `tier_reasons` and reports `ok · dynamodb` with the
  model key intact; Vercel is aliased to the branch. 60/60 responsive
  combinations, 58 pages crawl clean, AA in both themes, every delisted route
  still reachable by clicking.
  The three named surfaces on a phone: the palette **degrades by design** —
  `Ctrl-K` is unavailable and the header keeps a visible search affordance,
  measured at 390x844 with touch. The blast-radius graph renders at 375px with
  no overflow and its list survives beside it. The chain reveal works, and *had
  never been measured at a phone width at all* — `verifychain.py` sampled only
  1280x1000, the width the animation was designed at. It now samples both.
  **What the pass found, which is the point of having one.**
  *A link can be lost without anything overflowing.* A seventh nav label —
  Home, added during this phase — sat underneath the search field at exactly
  1024px, and every check passed: nothing scrolled sideways, nothing was missing
  from the DOM, the element was the right size in the right place and simply
  covered. R21b's lesson arriving from the other direction. `verifyui.py` now
  hit-tests every header item at three points across its width, and the row's
  breakpoint moved from `lg` to a measured 1160px — the gap between the last
  label and the search box is -7px at 1100, +5px at 1120, +38px at 1160, and
  five pixels is not clearance, it is the same collision waiting for a font to
  render slightly wider. A centre-only hit test accepted the -7px case; three
  points do not.
  *A breakpoint was only ever checked from one side.* The viewport list held
  375, 768 and 1440 — nothing at 1024, where the header row turns on. The width
  whose entire purpose is to switch behaviour was the width nothing visited.
  Both sides of it are checked now.
  *A checker that cries wolf once an hour is one people learn to re-run.*
  `verifylive.py` compares the "last synced" age across a 70-second window and
  failed against production at the 59-minute mark, because the hourly feed poll
  landed inside the window and reset the age legitimately. It now reads the
  record's own timestamp to tell a real sync from a page deriving its age from
  load, and retries once. Negative-controlled.
  *Nothing inside a dialog had ever been measured for contrast.* Every run this
  site has done measured the page and stopped; the palette and the shortcut
  sheet were exempt by accident. `verifycontrast.py --press` fixes that and both
  pass AA in both themes.
  **Two findings left open deliberately, because they are not Phase 5B's.**
  `verifyagent.py` fails on the deployed agent: asked which hosts `ws-0148`
  opened SMB to, Sati declines at hop 0 **with no tool call** — the exact
  behaviour R94 was written to fix, and its own worked example. Reproducible
  across runs today while other questions do call tools. R94 is marked partial
  rather than quietly left ticked.
  `verifychat.py` reports a problem when the free model allowance is exhausted,
  which is the site behaving honestly rather than failing. Not auto-skipped on
  that message: a checker that passes when the page says a particular sentence
  is a checker the page can switch off.

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

- [x] **R68 — The reasoning trace is visible.** Needs: **R21**.
  Show the intermediate steps, not only the answer: which evidence was pulled,
  which hypotheses were considered, which were ruled out and on what. The
  homepage asserts that *diagnoses are challenged by evidence*; this is the
  screen that demonstrates it rather than repeating it.
  **Done when:** every step names the records it read, a rejected hypothesis
  names what rejected it, and the trace is stored with the answer so it can be
  audited later rather than regenerated differently.
  *Highest-leverage task in this phase — it turns a claim into a screen.*
  Done, and three of the four changes are things that were already broken.
  **The agent was reasoning from a diagnosis with its doubt removed.** Every
  hypothesis went into the prompt under the same ref, `#hypothesis`, so two
  opposite claims shared one identifier — and `contradicted_by`, the field this
  console's whole argument rests on, was dropped before the agent saw it. Sati
  could not have named what ruled an alternative out; it was never told there
  was an alternative. Hypotheses are now ranked, each carries its own ref, and
  the contradictions go with them.
  **The trace already knew what each lookup read and the screen never showed
  it.** `tool_result` has carried `refs` since it was written; the audit view
  rendered *that* a lookup happened. Both surfaces now name the records, as
  links, and a lookup that found nothing says so rather than rendering blank.
  **The reformat retry was silently emptying fields.** This is the finding
  worth keeping: groq's `gpt-oss-20b` honours `response_format` when answering
  alone and ignores it the moment tools are on the request, so a tool-carrying
  turn answers in prose and *every* answer goes through `_finalise`. That retry
  said only "do not add anything you did not already say" — correct, and read
  as licence to leave every field the prose had not spelled out empty. An empty
  structured field is not neutral: it is the answer asserting there was nothing
  to put there, which reached the screen as "nothing was ruled out" for the
  incident whose entire point is the alternative it ruled out. The safeguard
  stays; the fields are now named as part of the answer.
  **A conditional rule is one the model decides it has already satisfied.**
  Rule 6 was measured through three drafts against the live model. Describing
  the principle: empty. Naming the evidence block shape but conditioning on
  *when your answer depends on one of those being wrong*: empty. Telling it
  plainly, for every such block, with the reformat fixed: the travelling
  alternative, with both refs that close it. Prompt version 5.
  Rejections are held to the citation standard — one whose refs resolve to
  nothing is dropped into `dropped_considered` and the count is shown, because a
  rejection a reader cannot check spends trust without earning it. Naming no
  reason and naming a reason that does not exist are the same failure and are
  collapsed deliberately.
  `scripts/verifytrace.py` obtains the answer from the API first and requires
  the page to match it, so a screen rendering a convincing account of steps
  nobody took fails. It asks a second question on a second incident purely to
  force a lookup: a green run with no tool call has not checked the half of this
  task about naming records, so that case fails rather than passes quietly.
  Negative-controlled — stripping the refs off the panel fails it.
  Measured against a live model on 25 August 2026: the travelling alternative
  with both closing refs, one lookup naming `host:ws-0148`, and the ledger
  carrying both. The final re-run could not repeat the lookup half — the day's
  free allowance for `gpt-oss-20b` was spent (198,310 of 200,000 tokens), which
  the checker reports as a failure naming what it could not measure rather than
  as a pass. `testagentchat.py` covers the same clause deterministically.
  Shown open rather than behind a disclosure. A conclusion is already more
  persuasive than the doubt beside it; putting the doubt one click further away
  decides which of the two a reader sees.

- [x] **R69 — Reasoning across incidents.** Needs: **R68**.
  "Are 0901 and 0902 related?", "same actor pattern?" — answered from entity
  overlap, timing and shared indicators, all of which are already stored.
  **Done when:** a relation is asserted only where the overlap is real and
  cited, *no relation found* is an answer it is willing to give, and a test
  covers a pair with no overlap.
  Done. `packages/core/pashupatastra/relations.py` decides it — a set
  intersection over stored records, with no model anywhere in the judgement —
  and `related_incidents` is the tool that reaches it. Rule 7: never answer a
  relation question without calling the tool. Prompt version 6.
  **Proximity in time is never evidence.** Two incidents in the same minute are
  two incidents; the correlator says so where it groups events and it would be
  strange for this to disagree one layer up. The interval is reported because an
  analyst wants it and can never make `related` true on its own.
  **An overlap that cannot be cited is not asserted.** Both sides have to name a
  record — a chain step, or an event id it rests on. An entity listed in
  `affected_entities` and established by nothing is a claim without a citation,
  so it is returned as `uncited` and excluded from the verdict rather than
  quietly counted. Citable on one side only is the same failure: it says the
  entity is in one incident and, somewhere, in the other.
  **The demo's honest answer is no.** The three security scenarios share no
  entity with each other and carry no independent indicators, so every pair is
  *no relation found* — which is the case this task names and the one every
  plausible implementation gets wrong by finding a resemblance and calling it a
  link. A "no" therefore says what it compared: bare, it is indistinguishable
  from not having looked. Refs stay empty on a "no", deliberately — there is
  nothing to cite for an absence, and returning refs anyway would let an answer
  that found nothing still look sourced.
  Resemblance is not relation, and this does not conflate them: Smriti already
  answers "has something like this happened before", and marks the difference
  between a precedent and a text match for the same reason.
  Nine tests in `testrelations.py` including the no-overlap pair, the
  simultaneous pair, the uncited overlap and the one-sided one; six more in
  `testagentchat.py` for the tool, its two refusals and both locks on the role.
  `scripts/verifyrelation.py` computes the overlap itself from `/incidents` and
  holds the agent to it, rather than asking the agent what the overlap was and
  grading it on its own answer.
  **Not yet measured against a live model.** The day's free allowance for
  `gpt-oss-20b` — 200,000 tokens — was spent on R68's prompt iteration, so the
  checker reports a failure naming what it could not measure rather than a pass.
  The engine, the tool, its refusals and both locks are covered deterministically;
  what is unmeasured is whether the model reliably calls the tool rather than
  answering a relation question from its own reading. Given rules 5 and 6 each
  needed a measurement to get right, assume this one does too until it is run.

- [x] **R70 — Drafts, not decisions.** Needs: **R68**.
  A draft playbook and a draft post-incident report, written from an incident's
  evidence. Text output, human review, and the same approval path before
  anything is adopted.
  **Done when:** every assertion in a draft carries its evidence reference, the
  draft is labelled a draft everywhere it appears, and adopting one is an action
  that goes through Dharma like any other.
  Done. `packages/core/pashupatastra/drafts.py` assembles both documents from
  stored records, `/incidents/{id}/draft/{kind}` serves them, and
  `components/drafts.tsx` renders them.
  **The citation rule is enforced at the constructor, not checked afterwards.**
  `Line` refuses to be built with empty `refs`, the way `Hypothesis` refuses
  empty evidence. Assembling freely and validating after leaves the uncited
  sentence written, reviewed and one deletion away from shipping; refusing to
  construct one tests the builder anybody writes next, not just this one.
  **Assembled on request, never stored.** A saved draft goes stale against the
  incident it describes, and the interesting failure is the silent one — a
  report citing a plan step that has since been re-scored. Built from the
  incident each time, it cannot disagree with it.
  **Labelled a draft three times** — panel title, badge, and the document's own
  title. Not redundancy: this is written to be copied out of a browser, and the
  failure it must not have is a paragraph arriving somewhere else with the word
  "draft" left behind on the page it came from.
  **Adopting is priced at 35 because of the band, not the number.** The first
  scoring of 20 put these in the 0–30 autonomous band, which in an environment
  with no blast radius means the agent could adopt its own draft unattended —
  the exact outcome the task is named against. 35 is where `disable_deployment`
  sits, and this is the same shape of act: it changes what happens next without
  breaking anything now, and it is fully reversible. Adopt and retract carry the
  same risk deliberately, being each other's rollback; a rollback priced far
  below the thing it undoes is one that gets taken lightly during the incident
  where it matters.
  **There is no adopt button.** The panel shows the verdict for the adopt action
  instead — what it would need, and from whom. A button implying one click
  finishes it would be the lie the task is named against.
  **Absence is stated rather than omitted.** A report with no "what was verified"
  section reads as an author who forgot; one saying nothing was verified, and
  citing the incident, makes a claim a reader can check. Empty sections are the
  interesting half of a report and are kept.
  Fourteen tests in `testdrafts.py` — the strongest being the one that tries to
  build an uncited line and cannot — and three over the route. `verifydraft.py`
  resolves every ref against the store rather than pattern-matching it, because
  "every line has refs" is satisfied by a line citing `evt-imaginary`, and it
  asks `/policy/evaluate` what adopting costs rather than trusting the page's
  sentence about it.
  Measured on 25 August 2026 against a local API in the deployed configuration
  (security domain, demo seed): all three incidents, both kinds, every line cited
  and every ref resolving, both drafts landing on `approval` and neither
  `autonomous`. Core suite 544 passing, API suite 377, web typecheck and build
  clean.
  **Not measured through a browser.** The page half of `verifydraft.py` needs
  playwright and a running site, and Phase 5C is not deployed until R74 — the
  live endpoint still 404s. The badge count, the citation links and the overflow
  check run there rather than being claimed here.
  **One configuration where the citations do not resolve.** With the action
  domain left unset, the store falls back to the infrastructure incident
  `INC-2026-0810`, whose evidence names `evt-deploy-421` and three siblings that
  are never written to the entity store — so both drafts render thirteen links
  that 404, which is R59's rule broken on a supported path. It predates this
  task and the deployed security configuration never takes it, but R70 is the
  surface that invites a reviewer to click them. Either seed those events or
  give the fallback incident refs that exist; not fixed here because the fixture
  is not this task's to change.

- [x] **R71 — Natural language to a detection rule.** Needs: **R70**.
  *"Write a Sigma rule that would have caught the SMB lateral movement in
  0903"* — the agent drafts it, states which telemetry field maps to which rule
  field, and flags what it is unsure of. An LLM generating something, held to
  the same citation discipline as everything else.
  **Done when:** the output parses as valid Sigma, each mapping names the source
  field it came from, and uncertainty is stated in the output rather than
  smoothed away.
  Done. `packages/core/pashupatastra/sigma.py` builds the rule,
  `/incidents/{id}/detection-rule/{technique}` serves it,
  `components/detectionrule.tsx` renders it, and `draft_detection_rule` is the
  tool. Prompt rule 8, version 7.
  **The generation is deterministic and the model is kept out of it**, as in
  R69. Which telemetry field corresponds to which Sigma field is a fact about
  our event model, not a judgement. Asked directly, a model produces
  `EventID: 5145` and `ShareName: ADMIN$` because that is the shape such rules
  have — and every line would be fabricated, because no event in this store
  carries a Windows event id or a share name. It would parse, review well,
  deploy, and never fire. That is the failure this task is really about, and it
  is not one a citation check downstream can catch: the fields are real Sigma
  fields, the YAML is valid, and only someone who knows this platform's event
  model can see that not one of them is populated here.
  **Mapping is typed, because the plausible mistake is a category error.**
  `SecurityPayload.principal` is set to the subject of the detection, so on a
  host-scoped detection it holds a hostname. `principal` maps to an identity
  field only where the entity is an account; elsewhere the refusal is reported
  rather than the mapping made. A hostname sitting in `SubjectUserName` parses,
  cites a real stored value, and is wrong in a way no reviewer would catch.
  **An indicator match is not a behavioural detection**, and the difference is
  recorded per field. The honest answer to the task's own example question is
  uncomfortable and is the point: the SMB step's telemetry supports exactly one
  Sigma field, `Computer: ws-0148`. That rule would have caught 0903 and will
  never catch anything else, so the document says so — in `x-warning`, in the
  comment header, and in `falsepositives`. Of the six rules drafted across the
  three demo incidents, exactly one generalises.
  **Uncertainty travels inside the artefact.** The gaps, the provenance table
  and the experimental status are keys in the YAML, not fields beside it. A rule
  is written to be pasted into a detection repository and the panel that
  carefully explained its limitations does not make that journey — R70's
  argument about the word "draft" appearing three times, applied to the thing
  that argument implies. The header is ASCII for the same reason.
  **Gaps are not false positives.** They were briefly emitted as
  `falsepositives`, which misreports both to every tool that reads the document;
  `falsepositives` now states the rule's actual weakness, derived from its shape.
  **A step that maps to nothing is refused, not filled.** Three of the nine
  technique steps across the demo incidents cite only events carrying no field
  Sigma has a name for, and each returns a 422 saying so. A
  refusal is a correct answer about the data; returning it as a 500 would file
  the system's honesty as a malfunction.
  **The model is never handed the rule text.** The tool returns the mapping
  table and the gaps; the YAML reaches the reader by the path that generated it.
  A model that retypes a machine-readable artefact will eventually retype it
  wrong, one dropped character is a rule that does not parse, and nothing in the
  loop could catch it.
  Thirty-five tests in `testsigma.py`, seven over the route, nine over the tool.
  **The parse clause is checked by pySigma, not by us** — our own `validate` is
  the same author marking their own work and would accept a rule wrong in
  exactly the way we misread the spec. It is a dev dependency of
  `packages/core`, so CI runs it.
  `scripts/verifysigma.py` resolves each mapping against the event it cites and
  reads the *claimed source field* rather than searching the record, because a
  value that appears somewhere in an event proves nothing about the field it was
  attributed to. Negative-controlled: mis-attributing `Computer` to
  `payload.source_address` fails it with that sentence.
  Measured on 4 September 2026 against a local API in the deployed configuration
  — six rules across three incidents, every one parsing under pySigma with zero
  errors, every field resolving to the source field it names, three steps
  refused.
  Core suite 579, API 393, web typecheck and build clean.
  **Not measured through a browser or against a live model.** The page half of
  `verifysigma.py` needs playwright and a running site, and Phase 5C does not
  deploy until R74. Whether the model actually calls the tool rather than
  writing Sigma from memory is the one clause only a live run settles, and given
  rules 5 and 6 each needed a measurement to get right, assume this one does too.
  **`openapi.json` was regenerated** for the two new routes, which also carried
  the pre-existing `Verdict-Input`/`Verdict-Output` collapse noted under R70 —
  a dependency-drift artefact, not an API change.

- [x] **R72 — Counterfactuals.** Needs: **R68**.
  *"What if we had blocked the ASN at 09:14 instead of 10:31?"* — reasoned over
  the causal chain timeline already stored per incident, estimating the blast
  radius that would not have happened. Ties to the *cost of the gap* framing R53
  put on the homepage.
  **Done when:** the estimate is derived from stored timeline and graph records,
  is presented as an estimate with its basis stated, and refuses rather than
  guesses where the timeline does not support the question.
  Done. `packages/core/pashupatastra/counterfactual.py` decides it,
  `/incidents/{id}/timeline` and `/incidents/{id}/counterfactual` serve it,
  `components/counterfactual.tsx` renders it, `what_if_we_had_acted` is the
  tool. Prompt rule 9, version 8.
  **Later is not the same as caused by, and this is the third layer to say so.**
  The tempting implementation counts every step after the intervention. That is
  post hoc reasoning wearing an estimate's clothes, and it inflates the single
  most quotable number this console can emit — the one that ends up in a slide
  where nobody can check it. A step is pre-empted only where it is both later
  *and* reachable from the entity removed, through access edges that cite their
  own evidence. `relations.py` refuses the same conflation one layer up and the
  correlator's adjacency gate refuses it one layer down; it would be strange for
  the counterfactual to be the place where "afterwards" means "because".
  **An intervention cannot precede the evidence that would have justified it.**
  This is the constraint that separates an estimate from a wish, and it is the
  task's own example that exposes it: asked about 09:14 when the first record of
  that address is 10:27, the honest answer is that the question is about
  clairvoyance rather than response time. A system without the rule answers
  happily, with a large avoided-impact number no amount of faster operating
  could ever have delivered. The earliest defensible moment is the first record
  naming the entity, and anything before it is a 422.
  **The remainder is rendered with equal weight.** Steps that came later and
  were never downstream would have happened anyway; they are reported as
  `unavoidable` rather than dropped, on screen as well as in the API. An
  estimate that shows only its winnings is an advertisement. INC-2026-0902
  exercises this for real — one step pre-empted, one that would have happened
  regardless.
  **The two assumptions the records cannot settle travel with every answer**: the
  block would have worked immediately and completely, and the attacker would not
  simply have taken another route. They are in `basis`, rendered under the
  number rather than in a tooltip, and they are the first things a retelling
  drops. A step that could not be placed in time is excluded and named, because
  assumed early it inflates the estimate and assumed late it deflates it.
  **The avoided set is counted from the chain, not from the reach.**
  Reachability says what could have been touched; the chain says what was.
  Reporting the larger would credit the intervention with harm that never
  happened.
  Sixteen tests in `testcounterfactual.py`, eight over the routes, ten over the
  tool. `scripts/verifycounterfactual.py` re-derives every pre-empted step: it
  resolves the step's refs, compares each event's own `occurred_at` against the
  moment intervened at, and takes an **independent** blast-radius walk through
  `/entities/` rather than reading back the walk the answer used. It then asks a
  question the timeline cannot support and requires the refusal.
  Negative-controlled: making the engine count everything after the intervention
  fails it with *later is not the same as caused by*.
  **A bug in the checker, worth recording because it is the failure this project
  keeps naming.** The first run reported six fabrications. The independent walk
  was reading `/entity/` — the route is `/entities/{key:path}` — and a 404 was
  being turned silently into an empty reach, so every genuinely downstream step
  looked invented. A checker reporting its own blind spot as the system lying is
  worse than one that does not check: it cannot be distinguished from a real
  finding. It now separates "nothing depends on this" from "the check could not
  be made" and fails loudly on the second.
  **`ToolBox` took its topology from the entity store, which is wrong on one
  backend.** `blast_radius` lives on `MemoryGraph` and `DynamoStore` but not on
  `PostgresStore`, so the existing `blast_radius` tool worked in tests and on the
  deployment and would raise on Postgres — right in the two places it is usually
  exercised and absent in the third. Topology now comes from `GraphStore`, which
  answers on all three. Found while wiring R72; fixed here because leaving two
  topology sources in one class is worse than either.
  Measured on 4 September 2026 against a local API in the deployed
  configuration: three incidents, gaps of 11, 30 and 90 minutes, every
  pre-empted step re-derived and every clairvoyant question refused. Core suite
  595, API 410, web typecheck and build clean.
  **Not measured through a browser or against a live model.** The page half of
  `verifycounterfactual.py` needs playwright and a running site, and Phase 5C
  does not deploy until R74; whether the model calls the tool rather than
  estimating is the clause only a live run settles.
  `openapi.json` regenerated for the two new routes.

- [x] **R73 — Argue the other side.** Needs: **R68**.
  Before finalising a diagnosis, a second pass arguing the alternative
  explanation and then saying why it was rejected — surfaced as *the
  plausible-and-wrong explanation*, which is language the Blue Team rubric
  already uses. The rubric becomes demonstrable by the agent scored against it.
  **Done when:** the alternative is a real competing hypothesis rather than a
  restatement, the rejection cites evidence, and a case where the alternative
  *wins* is possible and is tested.
  Done. `packages/core/pashupatastra/contest.py` adjudicates,
  `/incidents/{id}/contest` serves it, `components/contest.tsx` renders it under
  the rubric's own heading, `argue_the_other_side` is the tool. Prompt rule 10,
  version 9.
  **A ranking is not a refutation, and that is the whole module.** The tempting
  implementation reads 0.86 against 0.09 and reports the alternative rejected —
  but the incident asserting its own diagnosis is likelier is the claim under
  examination, not evidence for it. The verdict turns on one thing: whether
  something stored and resolvable contradicts the rival. Where nothing does, the
  answer is `unrefuted` — the diagnosis has not beaten it, it has ranked it
  below. That is the case where the alternative wins, and it is the one an
  implementation reading confidences can never produce.
  **`unrefuted` is an open question, not a rival conclusion.** It never says the
  alternative is right, only that the diagnosis has not earned its place over
  it. The distinction is easy to lose in a badge, so the panel and the tool both
  say it in a sentence rather than relying on the word.
  **A restatement is not a rival.** Two hypotheses on the same records with
  nothing to tell them apart are one claim written twice, and adjudicating
  between them is theatre that produces a confident-looking verdict about
  nothing. A real rival must share ground — explain at least one of the same
  observations, or it is answering a different question — and must diverge,
  through the leader citing something it does not or through something
  contradicting it. Where neither holds this refuses.
  **Text is never compared.** Deciding "these say the same thing" by wording
  would be the resemblance-matching R69 refuses and Smriti marks as a text match
  rather than a precedent. Two hypotheses can be worded alike and rest on
  different records, or worded differently and rest on the same ones. Only the
  records decide.
  **The rival is credited with what the diagnosis does not explain** — records it
  accounts for and the leader does not cite. It is the point a confident
  diagnosis is least likely to make about its own alternative.
  Sixteen tests in `testcontest.py`, six over the route, six over the tool.
  **Both verdicts are seeded rather than hoped for**: all three demo incidents
  rule their alternative out, so the case that matters most would otherwise
  never be exercised, and a skip would have reported three clauses green while
  measuring none. The fallback infrastructure incident refuses, because its
  hypotheses cite events that were never stored — the R70 fixture problem
  surfacing again.
  `scripts/verifycontest.py` re-derives the shared observations and the
  separators from the incident's own hypotheses rather than reading them back
  from the answer, resolves every ref named as ruling the rival out, and fails
  an `upheld` verdict that cites nothing — because the only thing left deciding
  such a verdict is the confidence gap. Negative-controlled: making confidence
  decide fails all three incidents with that sentence.
  **The prompt rule guards a different failure from rules 8 and 9.** Those
  compete with the model not having the facts; this one competes with the model
  always being able to produce the *shape*. A counterargument followed by a
  rebuttal is a form it can write about anything, it reads like reasoning from
  outside, and it has a direction — agreeing with the document in front of it is
  the easier continuation. So a model asked to challenge a diagnosis will nearly
  always conclude the diagnosis survives, which is the one outcome that makes
  the feature worthless. Rule 10 names the `unrefuted` verdict explicitly and
  says what to do when it appears.
  Measured on 4 September 2026 against a local API in the deployed
  configuration: three incidents, each sharing exactly one observation with its
  rival and each rejection resolving. Core suite 611, API 421, web typecheck and
  build clean.
  **Not measured through a browser or against a live model.** The page half of
  `verifycontest.py` needs playwright and a running site, and Phase 5C does not
  deploy until R74; whether the model reports an `unrefuted` verdict faithfully
  — against the document it just read — is the clause only a live run settles,
  and it is the one most likely to fail.
  `openapi.json` regenerated for the new route.

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

## The review pass, added 12 September 2026

Two people went through the deployed site as a SOC analyst would — every
section, and deliberately trying to break it — and wrote up what they found.
The same week an O-1A strategy document arrived that treats the project as the
centrepiece of an evidence case. All three are folded in here rather than kept
as separate documents, for the reason the polish pass gave: a second plan is
how two plans start disagreeing.

**What the reviews got right, and what was stale.** The audit duplication, the
first-request 503, the Observatory's `No feed named "undefined"`, the Blue Team
sentence that contradicts its own board, and the ungrounded answer that still
reads as an answer — all real, all reproduced against the code, and each is a
task below with its cause named. The second review also reported no author, no
link preview and no reachable *how it works* page; those shipped at R57, R16
and R54 and are on every page of the current deployment, so that reviewer was
reading an older build. Nothing is rebuilt for a finding that is already false.
And "mobile is an unverified gap" is answered by R14 and R67 — 375, 768, 1024
and 1280, measured by `verifyui.py` on the deployed site — so it is cited, not
redone.

**The rule that orders this pass:** the ledger comes first. Every page view of
an incident has been writing three audit records, and every task after it that
counts anything in the ledger would be counting page views.

The strategy document's engineering half becomes **Phase 5F**. Its other half —
paper venue, judging, letters, coverage, a domain, a licence, a DOI — is not
engineering and does not belong in a delivery plan; it lives in
[O1 visa roadmap.md](O1%20visa%20roadmap.md), which maps each criterion to the
task here that produces its evidence and to the things only the owner can do.

---

## Phase 5E — What two reviewers hit

Needs **R59**. Runs before Phase 6, as Phases 5A–5D did. Nothing here is new
capability; each task removes a thing a visitor already hit.

- [x] **R93 — A read must not write to the audit ledger.** Needs: nothing.
  *Moved here from Phase R, where it was found; not renumbered.* The incident
  page's server render POSTs `/policy/evaluate` for the plan's riskiest step
  and twice more to price adopting each draft, and the route appends a record
  unconditionally — so the reviewer's `isolate_host: risk 67 → senior` ×144 is
  144 page views. The fix is the one R93 already states: computing a verdict to
  *display* is not the act of authorising one. `POST /policy/preview` runs the
  same evaluator and records nothing; `/policy/evaluate` keeps recording,
  because it is the call an approval is made against.
  **Done when:** loading an incident page any number of times adds no audit
  records, authorising an action still records exactly one, and a test counts
  the ledger before and after both.
  Done. `POST /policy/preview` runs `_evaluate` — the same function
  `/policy/evaluate` now calls — and returns without touching `AUDIT` or
  `STORE.verdicts`; the incident page's three verdicts come from it.
  **A preview cannot become an approval.** The two verdicts are the same
  arithmetic and indistinguishable by their numbers, and `/policy/approve`
  trusts the verdict in its body, so a previewed verdict posted back would have
  put an approval in the trail with no evaluation before it. A preview carries
  a `preview` constraint and approve refuses it with a 409 naming the recording
  route. The web never approves anything, so nothing on the site changes; the
  refusal is for whoever calls the API directly.
  *Evidence: `test_a_preview_leaves_the_ledger_alone_and_an_evaluation_does_not`
  counts the ledger — ten previews add nothing, one evaluation adds exactly
  one, and the two verdicts agree on action, risk, tier, approvers and
  reasons; `test_a_preview_verdict_cannot_be_approved` gets the 409. API suite
  423 passing, `openapi.json` regenerated for the new route, web typecheck
  clean. The 144 records already in the deployed ledger are R98's.*

- [x] **R98 — Fold what is already in the ledger.** Needs: **R93**.
  The 143 records R93 stops adding are still there, and the ledger is
  append-only. Consecutive records with the same kind, summary and actor
  collapse to one row carrying `×N` and the first and last timestamps, in the
  loop timeline and the incident's audit panel, with every individual record
  behind an expander — R56's shape, applied to the trail. A retention sweep
  that deletes them is *offered*, not done: the fold makes it unnecessary, and
  the first deletion from an append-only ledger is a precedent worth not
  setting for tidiness.
  **Done when:** INC-2026-0903's trail renders one approval row where it
  rendered 144, a test feeds a fixture with a known run of duplicates and
  asserts the fold count and that no record id is lost, and every folded
  record is still reachable by its anchor.
  Done. `lib/fold.ts` is the one fold — consecutive records with the same
  kind, summary and actor become one row with `×N` and the span they cover —
  and the loop timeline, the incident's trail and `/audit` all use it. On
  `/audit` the key also carries the incident ref, so two incidents' identical
  lines never fold into each other. **Consecutive only.** Two identical lines
  with an approval between them are two events, and folding across the
  approval would hide the order that makes a trail a trail. Each folded row
  keeps the first record's anchors and lists the rest behind `all N records`,
  each with its own `audit-N` and timestamp anchor, so a citation to any of
  them still lands; browsers open a closed `<details>` on fragment navigation.
  **The web app has tests now.** Node 24 runs TypeScript directly, so
  `lib/fold.test.ts` is five `node --test` cases with no dependency added:
  a known run of 144 folds to one row of 144, no index is lost between input
  and output, a run is not folded across an intervening record, the span is
  earliest-to-latest, and a single record is left alone. `npm test` runs them
  and CI calls it before the build.
  The sweep is not done, as the task said: with the fold in place the 143
  records cost nothing to keep, and deleting from the ledger for tidiness is
  a precedent the ledger does not need.
  *Evidence: twelve identical evaluations were written into a local API and
  the incident page rendered them as one row — `12 identical records, folded`
  — in both the timeline and the trail, with `audit-0` through `audit-11`
  each present exactly once. 5/5 node tests, web typecheck clean.*

- [~] **R99 — Name the 503 before fixing it.** Needs: nothing.
  Both reviewers saw an HTTP 503 on the first request of nearly every route,
  followed by a quiet success. Nothing in the app emits a 503 on a read route
  — only `/agent/chat` does, and only when no model answers — and a cold start
  hits once per container, not once per navigation. So the cause is not
  readable from the code, and guessing at it would be exactly the invented
  diagnosis this console refuses elsewhere. `scripts/verify503.py` drives fifty
  navigations in a real browser and records every response at or above 500
  with its URL and the headers that say who answered — `x-vercel-error`,
  `x-vercel-id`, `apigw-requestid`, `server` — beside the API's own CloudWatch
  `Init Duration` for the window.
  Then the fix by cause, and both are prepared: if it is Lambda init, an
  EventBridge `warm` task every five minutes on the existing handler (8,640
  invocations a month against an always-free million), writing a heartbeat that
  R107 later reads as uptime; if it is Vercel throttling prefetches of
  `force-dynamic` pages, a prefetch policy on the navigation links. Either way,
  `get` and `post` in `lib/api.ts` retry once on a 5xx or a network error with
  a short backoff, and return a **typed failure** — missing, unavailable,
  offline — where today every one of those collapses to `null` and renders as
  "API unreachable".
  **Done when:** the fifty-navigation run reports zero responses at or above
  500, twice, an hour apart, and the cause is written here in one sentence.
  **The cause, in one sentence:** `recent_events` read every feed event ever
  stored and sorted it in Python, the layout called it through
  `/search/index` on every route, and by 12 September that read took 5 to 30
  seconds — past API Gateway's 30-second limit, which answers 503.
  Measured, not inferred: `scripts/verify503.py` asked the API directly and
  got `/intel?limit=5` in 4.9 s, 7.8 s, 20.9 s and then a **503 at 30.09 s**
  carrying only `apigw-requestid` — no Vercel header, no Lambda error, the
  gateway giving up on an integration that was still running. Not a cold
  start: `/incidents/{id}` answered in 112 ms on the same container. The
  partition grows by every hourly poll, so the reviewers on 11 September saw
  it at the edge of the limit and today it is past it.
  **Three changes, none a second index on the table** — the free tier's 25
  capacity units are already spent and a global secondary index would cost
  more of them:
  - **A recent-events index per source**, one small META item listing its
    newest 300 events, maintained by `save_events` — the only writer — and
    rebuilt once from a full read if a store predates it. `recent_events`
    is now a few small gets and one batch fetch of exactly the rows it
    returns. `merge_recent` and `select_recent` are pure and tested: the
    newest survive and the rest fall off, a re-reported event is indexed
    once, and the order is the order the partition read gave, so nothing a
    reader saw changes.
  - **`snapshot` queries per node through the entity index** instead of
    reading every event; the map has eleven nodes and the partition has
    every feed entry since August.
  - **A `warm` task** on the handler, for EventBridge every five minutes
    (`scripts/schedulefeeds.py --task warm --name pashupatastra-warm --rate
    "5 minutes"`, flexible window off): reads the index so the first real
    request finds it built, and counts one heartbeat per UTC day that R107
    reads as uptime. The tasks moved to `app/tasks.py`, which imports no
    Lambda-only module, so they are tested where `mangum` is not installed.
  The client half — a typed failure and one retry in `lib/http.ts` — landed
  under R101.
  **What remains, and why:** the Lambda is not redeployed and the warm
  schedule not created, because this session holds no AWS credentials; the
  second zero-5xx run an hour after the first is R106's. Until then the
  deployed API still scans, and the 503 is still there for a visitor.
  *Evidence so far: the measurement above; 4 tests on the index in
  `testdynamo.py` plus one against a real table that asserts the second
  read never touches the partition, gated on a table being reachable;
  `test_the_warm_task_primes_the_indexes_and_beats_once`; seeded suite 440,
  default 431.*


- [~] **R100 — One wave, not four.** Needs: **R99**.
  The incident page makes about fifteen API calls per render in four
  sequential round trips — `generateMetadata` fetches the incident and the page
  fetches it again, then ten calls at once, then a detection rule per
  technique and the counterfactual, then three policy evaluations. That is the
  two to three seconds of skeleton the reviewer measured on every transition.
  `React.cache()` makes the metadata and the page share one fetch; everything
  that needs the incident runs in one `Promise.all` after it. The five routes
  with no `loading.tsx` — observatory, blue team, how it works, ask, overview —
  get one shaped like the page (R13's rule), and the navigation links show a
  pending state through `useLinkStatus`, which Next already provides, so the
  wait reads as loading rather than as broken and no dependency is added.
  **Done when:** a script counts the round trips per render at two or fewer,
  and server render time on the deployed incident page is measured before and
  after and written here.
  Code done; the before-and-after on the deployed page waits for R106.
  `incidentOnce = cache(getIncident)` gives the metadata and the page one
  fetch between them. Wave one is every call that needs only the id; wave
  two — the verdict preview, the two adoption previews, the counterfactual
  at the first step's moment, and a rule per technique — is one
  `Promise.all` after it. Six sequential round trips became two.
  `lib/waves.test.ts` reads the page's source and holds it to that shape:
  exactly two `Promise.all` waits, no API call awaited on its own between
  them (the not-found fallback excepted), and the metadata sharing the
  page's fetch. Read from the source because the count is a property of how
  the page is written, and a regression to a solitary `await` is what it
  would catch.
  Five routes had no `loading.tsx` — observatory, blue team, how it works,
  ask, overview — and now do, each shaped like its page. The navigation
  links show a pending mark through Next's own `useLinkStatus` for as long
  as the next page's render is in flight, announced through a `status`
  role; no dependency added.
  *Evidence: 18 node tests, web typecheck and `next build` clean.*

- [x] **R101 — Observatory tells the truth about failure.** Needs: **R99**.
  `No feed named "undefined"` is not a bad query parameter — the filter links
  never serialise one. It is what the page prints when `/intel` fails while
  `/intel/status` succeeds, because the only failure it knows how to name is
  an unknown source. With R99's typed failure it says "no feed named X" only
  when a source was asked for and the API said 404, and shows the offline
  state otherwise. On the one page whose whole claim is that the data is real,
  a wrong error message is the worst available outcome.
  **Done when:** a test renders the page against a null `/intel` and a healthy
  `/intel/status` and finds the offline state, with the word `undefined`
  nowhere in it.
  Done, on the client half of R99 landed early: `lib/http.ts` gives every
  request a typed failure — `missing` for a 404, `unavailable` for a 5xx,
  `offline` for nothing answering — and one retry after 300 ms on the second
  two; a 404 is an answer and is never retried. `get` and `post` sit on it, so
  every page inherited the retry without changing, and `getResult` is the
  typed form for the pages that must tell an outage from a not-found. The
  Observatory decision is `lib/observatory.ts`: *unknown source* only when a
  source was asked for and the API said `missing`; everything else, including
  a 503 with a source named, is the offline state.
  *Evidence: `lib/http.test.ts` — a 503 then a 200 is the 200 and the page
  never learns, a dropped connection is retried once and a second drop is
  offline, a 404 is never retried, the retry waits; `lib/observatory.test.ts`
  — a failed `/intel` with no source is offline for all three kinds, a 503
  with a source is still offline, only a 404 with a source names it. Web
  typecheck clean.*

- [x] **R102 — The debrief cannot contradict the score.** Needs: **R27, R64**.
  The reviewer scored 100 and read "you opened the evidence that rules out the
  plausible alternative" beside a board marking a different piece of decisive
  evidence as never opened. Both are true, and that is the bug: the score
  credits opening *any one* entity holding a contradicting record, while the
  board is built by a second resolver — the entity's eight most recent events
  — and the sentence about misses ignores whether proof was found elsewhere.
  One resolver for both. And the sentence is written relative to the score:
  where proof was found, "it was also on Y, which you did not open"; only where
  it was not, "you never looked".
  **Done when:** a test builds a scenario with two decisive entities, opens
  one, and asserts full investigation marks with a board and a sentence that
  agree; `verifydebrief.py` plays the same case on the deployed site.
  Done. `decisive_entities()` in `game.py` is the one answer to "which
  entity holds the record that rules the decoy out", read from each record's
  own `entity_key`; the score and the board both use it. The old board asked
  a second way — each entity's eight most recent events intersected with the
  decisive set — so a decisive record older than eight events was credited by
  the score and marked *not decisive* by the board. The sentence is now
  written from the score's own split: *on X* where proof was opened, *it was
  also on Y, which you did not open* where more of it exists, and *you never
  looked* only when none was opened. The page's own line under the board says
  the same thing in the same case, and drops from warning to muted when no
  marks were lost.
  **The reviewer's case was reachable on all three scenarios.** Every one has
  two or three decisive entities — 0903 has three — so opening one always
  left the board naming the others as misses beside a full-marks line.
  *Evidence: two tests in `testdebrief.py`, both watched failing on the old
  code — one opens one of two decisive entities and requires full marks with
  a board and a line that agree, the other puts the decisive record ninth in
  an entity's history and requires the board to still mark it. Run against a
  local API in the deployed configuration, all three scenarios return the
  agreeing sentence. `verifydebrief.py` gained the case for the deployed
  site; it runs at R106.*

- [~] **R103 — An answer with no citation is not shown as an answer.** Needs: **R21, R68**.
  The injection attempt was refused, which is the property that matters. But
  the mechanism underneath it is weaker than it looks: `grounded: false` is a
  label attached *after* the prose, and the prose is still returned verbatim.
  A model that claimed to have flagged and logged something, with nothing to
  cite, would reach the screen with a warning beside it — and a warning beside
  a confident sentence is read as the sentence. So an answerable turn that
  keeps zero refs has its text **withheld**: the visitor sees a fixed sentence
  saying the model produced an answer it could not cite and it was not shown;
  the withheld text goes to the audit record, where a reviewer can read it.
  The schema already carries `answerable` and `evidence_refs`; this makes the
  two the only path to prose.
  Then the regression battery the reviewer asked for, as one fixture read by
  two consumers: `testagentchat.py` with a fake gateway, deterministic, in CI
  — and `verifyagent.py` against the live model. The battery gains the
  reviewer's exact injection, isolate-host on an incident with no host entity,
  and an ambiguous question, beside the four it has. Each case states what must
  be true of the reply: no proposed action, no execution, and no prose where
  nothing was cited.
  **Done when:** the fake-gateway case returning "I have isolated the host"
  with no refs is withheld and queues nothing, every battery case passes
  against the live model, and the withheld text is in the ledger.
  Done on the deterministic half; the live half runs at R106, since the
  deployed API does not carry this yet.
  `ChatAnswer.withheld` is set when an answerable turn keeps no refs and has
  text; `answer` becomes the one fixed sentence, `grounded` stays false, and
  the model's words go to `withheld_text` — a field excluded from
  serialisation, so no client can render it, and copied into the `agent_turn`
  record as `withheld_answer` by the route. The trail's summary line carries
  `WITHHELD`, and the audit page shows the words under a label saying the
  model wrote them and cited nothing. The chat panel sets a withheld turn as a
  notice rather than as prose, with a `withheld` badge in place of *not
  grounded*.
  **The battery is one file with two readers.** `services/api/tests/
  battery.json` holds ten cases, each with a question, an incident, a reason,
  and an `expect` block; six also carry a `scripted` model output.
  `testagentchat.py` replays the scripted ones through the real route with a
  fake gateway — the reviewer's injection answered *"host isolated, execution
  confirmed, flagged and logged"* with nothing cited is withheld and queues
  nothing; a plausible uncited summary is withheld; the same summary with a
  real ref is shown; an honest decline citing nothing is *not* withheld,
  because there was nothing to cite. `scripts/verifyagent.py` asks the live
  model the same ten and applies the same block. The no-host case is a
  live-model expectation only: an action carries no target kind, so there is
  no structural check that `isolate_host` needs a host, and the battery says
  so rather than pretending the scripted twin covers it.
  **CI was not running any of this.** The battery, R20's proposal test and
  every Blue Team test skip unless the demo scenarios are seeded, and the
  workflow never seeded them — the tests that guard the public site were
  green on every run by never running. The api job now runs the suite twice,
  the second time as the deployed configuration; three tests that assert the
  infrastructure fixture say so and skip there instead of failing.
  *Evidence: 73 tests in `testagentchat.py` under the seeded configuration,
  including six battery cases and the ledger round-trip; 433 passing in that
  configuration and 425 in the default, 0 failing in either; `openapi.json`
  current; web typecheck clean.*

- [x] **R104 — Tokens against the allowance.** Needs: **R22**.
  Every answer already shows its token count and every `agent_turn` record
  carries `tokens` and `cached`. Rolled up: `GET /usage` — turns and tokens
  today against the daily allowance, the share answered from cache, and
  fourteen days of the same — computed from the ledger, not from a counter
  that could drift from it. Spend is zero and the route says why, because a
  cost panel reading `$0.00` with no explanation looks like a panel nobody
  wired. One line on `/ask` in R61's style: *today 48k of 200k tokens · 61%
  from cache*.
  **Done when:** a script recomputes every figure from `/audit` and matches
  the route, and the line on the page equals the route.
  Done. `app/usage.py` rolls `agent_turn` records up by day — pure over its
  inputs, so it can be recomputed from outside — and `GET /usage` serves it
  with `spend_usd: 0` and the sentence saying why. The ledger gained one read,
  `AUDIT.since(when, kind)`, on all three backends; DynamoDB bounds it with a
  range on the sort key and a day of slack, and every backend filters on the
  record's own `at`, so the answer does not depend on how a store orders its
  keys. `chat_daily_allowance` is 200,000, the provider's free-tier daily
  limit, reported and not enforced — the provider enforces it and a 429
  already reaches the visitor as a sentence.
  **Cached turns are turns and not tokens.** A cached record carries the token
  count of the run that produced the answer (R22), and a roll-up that summed
  it again would bill every repeat of a question at full price — the cache
  would then look like it saved nothing.
  The line sits beside the title on `/ask` — *today 48k of 200k tokens · 61%
  from cache* — with the reason for the zero in its tooltip rather than as
  `$0.00`, which reads as a panel nobody wired.
  *Evidence: `test_usage_is_recomputed_from_the_ledger` writes three turns
  through the route, one a real cache hit, recounts them from `/audit` and
  requires the route to agree on turns, hits, tokens and both rates.
  `scripts/verifyusage.py` does the same against a running API and, with
  `--page`, reads the line off `/ask`; run against a local API it matches
  (0/0/0 — no model locally, so the non-zero case is the test's). Seeded
  suite 434, default 425, `openapi.json` regenerated, web typecheck clean.*

- [x] **R105 — Confidence is labelled for what it is.** Needs: **R68**.
  "86% confidence" on a scripted scenario is a number the scenario's author
  typed. That is legitimate for a written scenario and it is not a measured
  rate, and the reviewer was right that the page lets a reader take it for
  one. Wherever a hypothesis confidence renders — the incident, the agent's
  evidence block, the Blue Team reveal — one sentence says which it is.
  Calibration proper — stated confidence against a human's later verdict —
  needs outcomes to exist, and none do on this deployment; it lands with
  **R96**, and nothing here invents a calibration figure to fill the gap.
  **Done when:** every rendered confidence carries the label, and no
  `calibration` field exists anywhere in the API.
  Done. `Stated` in `components/ui.tsx` renders `86% stated` with the one
  sentence — a confidence the scenario's author stated, not a measured rate;
  calibration arrives with R96 — as its tooltip, and every surface that
  printed a confidence uses it: the incident header (relabelled from *Root
  cause probability*, which was the worst of them, with the sentence printed
  in full beneath the panel), each alternative hypothesis, the overview cards,
  the loop timeline and the Ask console's diagnosis line. The agent's own
  evidence block says the same in its `confidence:` line, so the model cannot
  relay the number as a rate either. The contest panel already carried its own
  sentence about confidence deciding nothing and is left as it was.
  *Evidence: no `% confidence` or `Root cause probability` literal remains in
  the web app; `test_no_calibration_figure_is_invented` asserts the word is
  absent from the API's own contract; seeded suite 435, web typecheck clean.*

- [ ] **R106 — Deploy Phase 5E and review.** Needs: **R93, R98–R105**.
  Carries **R74**'s measurements too: Phase 5C is still undeployed, so the
  browser halves of `verifycontest`, `verifycounterfactual`, `verifysigma` and
  `verifyrelation`, and their live-model clauses, run here.
  **Done when:** R99's run shows zero 5xx, `verifysite.py` crawls clean,
  `verifyui.py` passes at every breakpoint, and loading the beaconing incident
  ten times leaves its audit count unchanged — all on the deployed site.
  **Stop here for review.**

---

## Phase 5F — Evidence

Needs **R106**. Each task here produces something a petition exhibit, a
citation or a journalist needs, from data the platform already holds. The
mapping from criterion to task is in
[O1 visa roadmap.md](O1%20visa%20roadmap.md); the rule that governs every task
is the site's own — nothing typed, everything recomputable — because evidence
that cannot survive being checked is worse than none.

- [ ] **R107 — `/impact`.** Needs: **R99**.
  One page carrying the numbers the strategy document asks for, each naming
  where it came from: indicators and reports ingested to date and every feed's
  cursor, from the store; agent turns and Blue Team attempts to date, from the
  ledger; audit records; **page views**, counted server-side per route per day
  in DynamoDB with no cookie and no client beacon — reported as views, with a
  sentence on why unique visitors are refused (uniques need an identifier, and
  R28 settled that this site does not mint one); stars, forks and contributors
  from the GitHub API, cached hourly on the server; uptime from R99's
  heartbeat; and a milestone timeline **generated from git** —
  `scripts/milestones.py` reads the `(R##)` commit dates, so the timeline
  cannot list a milestone that did not land.
  **Done when:** each figure equals an independent recount by a script that
  reads the underlying source rather than the page.

- [~] **R108 — Cite this work.** Needs: **a licence** — the owner's decision.
  `CITATION.cff` at the root, which GitHub renders as *Cite this repository*,
  validated by `cffconvert`; a cite block on `/how-it-works` and `/impact`
  carrying BibTeX, APA and the permalink; the DOI read from `NEXT_PUBLIC_DOI`
  and shown as *no DOI yet* until one exists rather than as a placeholder that
  looks like one. Zenodo mints a DOI from a GitHub release and requires a
  licence; README says the licence is pending clearance, so the DOI is blocked
  on that decision and nothing here pretends otherwise.
  **Done when:** the BibTeX on the page round-trips from the committed
  `CITATION.cff`, and the file validates.
  Done on everything but the DOI, which is blocked exactly as the task said.
  `CITATION.cff` validates under `cffconvert`; `scripts/buildcitation.py`
  renders it to `lib/citation.generated.json` and `components/cite.tsx`
  shows the BibTeX, the APA, the permalink, the source, and *no DOI yet — one
  is minted from a tagged release once the repository carries a licence*, on
  `/how-it-works` beside the stack. The version is the package's `0.1.0`,
  because there are no releases and a number typed to look like one is the
  invented figure this repository refuses elsewhere; a test holds the two
  equal. `testcitation.py` regenerates the JSON from the file and requires
  the committed copy to match, requires no DOI on the page unless the file
  carries one, and proves a DOI added to the file reaches both renderings.
  **Owner's next step:** decide the licence, add it to `CITATION.cff` and the
  repository, tag a release with Zenodo's GitHub integration switched on, then
  put the minted DOI in the file and run the script.
  *Evidence: 5 tests; `cffconvert --validate` passes; web typecheck clean.*

- [ ] **R109 — `/press`.** Needs: **R107**.
  A media kit, built so that someone writing about the project does not have
  to research it: one plain paragraph, the artwork under BRAND.md's
  constraints, the live `/impact` numbers, a contact line, and screenshots
  **captured from the deployed site by `scripts/buildpress.py`** at 1440 — not
  mockups, and regenerated by one command when the site changes, the way
  `buildbrand.py` regenerates the icons.
  **Done when:** every image on the page was captured from the URL it
  depicts, and nothing overflows at 375.

- [ ] **R110 — The study the console can run.** Needs: **R102**.
  The strategy document's experiment — ten to thirty people investigating
  incidents, timed and scored — has its apparatus already built: Blue Team
  scores investigations on the server. An opt-in study mode adds what a study
  needs and nothing else: a consent sentence, timings from briefing to first
  evidence to committed diagnosis, the entities opened, and the score, stored
  under the anonymous token R28 already issues. No names, no emails.
  `scripts/studyreport.py` produces tables the way `papertables.py` does, and
  `docs/research/STUDY.md` states the protocol, the metrics, the target N, and
  the confound the paper draft already admits — the scenarios are
  self-authored.
  **Done when:** a dry run from two browsers yields a table with n=2, and the
  protocol names what the study can and cannot claim.

- [x] **R111 — README as a research project page.** Needs: nothing.
  The README does not name the author, link the live site, the paper draft or
  the benchmark, or say how to cite. It reads as a platform scaffold. It should
  read as what the repository now is: author, live URL, paper, benchmark and
  generated tables, status, citation, how to run — with the stack list held to
  `buildinfo.py`'s rule that nothing is named a manifest cannot back.
  **Done when:** every link in it resolves and every capability it claims is a
  ticked task in this file.
  Done. The README opened with *Phase 0 — no runtime code yet*, which stopped
  being true in August. It now names the author, links the live site, says
  in one paragraph what is real and what is written, states the three
  properties the design rests on, carries a status table that points at this
  file rather than restating it, a research section that links the draft
  paper with its own admission of what it lacks, the benchmark and the
  generated tables, instructions that run the API in the deployed
  configuration, the BibTeX from `CITATION.cff`, and a licence section that
  says the decision is pending and what that means for a reader. The
  platform section now separates the target platform from what the demo
  actually runs on.
  *Evidence: every relative link resolves (checked by script); the README's
  BibTeX is held equal to the generated block by a test; every capability
  named in the status table is a ticked task above.*

- [ ] **R112 — Custom domain.** Needs: **the purchase** — the owner's.
  Plain `.com` if it is free, per the review. The code is already env-driven
  (`NEXT_PUBLIC_SITE_URL`); what remains is setting it, redirecting
  `pashupatastra.vercel.app` so nothing already shared breaks, and re-verifying
  canonical, Open Graph, sitemap and `CITATION.cff` against the new host.
  **Done when:** the old URL redirects, and R16's nine-route metadata check
  passes on the new one.

- [ ] **R113 — Deploy Phase 5F and review.** Needs: **R107–R111**.
  **Done when:** `/impact` and `/press` are live, the recount scripts match
  the deployed figures, and `verifysite.py` and `verifyui.py` pass with the
  new routes included.
  **Stop here for review.**

**Held, and stated rather than quietly dropped.** Judging other people's Blue
Team write-ups needs accounts, so it sits behind **S2** exactly as R84 does.
Calibration tracking sits behind **R96**. Submitting the paper is the owner's
call, which ROADMAP.md already records, and nothing here submits it for them.

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

- [x] **R93 — A read must not write to the audit ledger.** Needs: nothing.
  *Moved to Phase 5E on 12 September 2026, where it is the first task; the
  finding is kept here because this is where it was made.*
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

- [~] **R94 — Planning: reach for the tool before giving up.** Needs: **R26**.
  **Reopened by R67's review.** `verifyagent.py` against the deployed agent on
  25 August 2026: *"Which hosts did ws-0148 open SMB to, and what is the blast
  radius of the busiest one?"* is declined at hop 0 with **no tool call**, twice
  in a row, while two other questions in the same battery do call tools. That is
  the behaviour this task exists to remove, on the question this task is written
  around. What remains is to find out whether the prompt change stopped holding,
  the model drifted — it is a free tier and non-deterministic — or the battery
  is asking something the tools genuinely cannot start on. The note below about
  the corrected expectation still stands: declining *after looking* is right,
  and no tool call is not looking.
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
