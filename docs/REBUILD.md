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
```

---

## Phase 1 — Re-theme the domain

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

- [ ] **R4 — Security action registry.** Needs: nothing.
  Register the 14 actions from the prompt's table with their risk scores,
  rollbacks and post-states. Tag every action with a domain
  (`infrastructure` | `security`) and serve one domain per deployment.
  `wipe_host` at risk 100 registers as irreversible so Dharma can deny it
  explicitly — the same way `delete_infrastructure` already does.
  **Done when:** `GET /api/v1/actions` returns the 14 security actions and no
  infrastructure ones; a test asserts `wipe_host` is never granted autonomously
  at any confidence.

- [ ] **R5 — Three scripted incidents.** Needs: **R2, R3, R4**.
  Credential stuffing, phishing → token theft, lateral movement / beaconing.
  Each with a causal chain carrying evidence ids and ATT&CK techniques, a
  diagnosis, at least one alternative hypothesis *contradicted by named
  evidence*, and a risk-gated plan.
  The phishing one must propose `revoke_session` + `quarantine_email` and **not**
  `force_password_reset` — that distinction is the scenario's whole point.
  **Done when:** all three load through the API and render end-to-end, and a
  test asserts each one's contradicted hypothesis cites real evidence ids.

- [ ] **R6 — Make evidence resolve.** Needs: **R5**.
  *This is a live defect, not a new feature.* The current incident cites
  `evt-deploy-421`; no such event exists in the store, so the citation is
  unfollowable text. Seed the events each incident cites, add
  `GET /api/v1/events/{id}`, and make evidence tags links.
  Also fix: a causal-chain link to an entity not in the graph currently renders
  **"API unreachable"**, telling the visitor the whole system is down when the
  API is fine.
  **Done when:** every evidence id on every incident resolves to an event with
  its provenance; a missing entity renders "not found", not "unreachable".

- [ ] **R6b — Fix the hydration mismatch on Infrastructure.** Needs: nothing.
  Found by `scripts/verifyui.py` while verifying R1: `/infrastructure` throws
  React error #418 — server-rendered HTML not matching the client — at all
  three viewports. The page renders, so it is invisible until something on it
  silently stops updating.
  **Done when:** the route loads with no page error at 375px, 768px and 1440px.

- [ ] **R7 — Microcopy pass.** Needs: **R5**.
  Every sentence referencing deploys, services, replicas or databases rewritten
  for the security domain, keeping the existing voice. Includes the "reading
  this map" text, the Infrastructure page framing, and the offline notice.
  **Done when:** a grep for the SRE vocabulary across `apps/web` returns only
  intentional hits, listed in the task summary.

- [ ] **R8 — Deploy Phase 1 and review.** Needs: **R1, R6, R7**.
  Build, deploy both halves, walk every page.
  **Done when:** the live site shows three security incidents, security actions
  only, resolving evidence, and no SRE language. **Stop here for review.**

---

## Phase 2 — Make it look finished

Needs **R8**. Read the frontend design skill before touching a component.

- [ ] **R9 — Typography.** Needs: **R8**.
  One deliberate pairing: a technical monospace for ids, evidence tags, risk
  scores and timestamps; a clean sans for prose. Self-hosted or Google Fonts,
  with a real fallback stack.
  **Done when:** applied consistently across all pages, and no element still
  falls back to the browser default sans.

- [ ] **R10 — Status and contrast pass.** Needs: **R8**.
  Keep the ▲ ◆ ● ○ system — it already encodes status by shape as well as
  colour. Verify every status token against both themes.
  **Done when:** every status pairing meets WCAG AA (4.5:1 for text, 3:1 for
  the glyph) in light and dark, with the measured ratios reported.

- [ ] **R11 — Scenario picker.** Needs: **R5, R8**.
  The prompt calls this the single highest-value UI change, and it is: today one
  incident exists, forever. A control that spins up any scenario on demand turns
  a screenshot into something a visitor clicks through.
  **Done when:** a visitor can switch between all three incidents from the UI,
  and each lands with its own entities, events and audit trail.

- [ ] **R12 — Real empty states.** Needs: **R11**.
  Audit's "Nothing recorded yet" and Overview's "No activity recorded yet" are
  one flat sentence each. Keep the sentence — it is good — and give it an icon
  and a next action, which after R11 is "run a scenario".
  **Done when:** every empty state on every page offers a next action.

- [ ] **R13 — Loading and transition states.** Needs: **R9, R10, R11**.
  Skeletons for incident and infrastructure so switching scenarios feels
  responsive. `Skeleton` already exists in `components/ui.tsx` and is unused.
  **Done when:** switching scenarios shows a skeleton, never a blank frame.

- [ ] **R14 — Mobile pass.** Needs: **R9, R10**.
  The dependency table and causal chain at 375px; tables break first.
  **Done when:** no horizontal page scroll at 375px on any route, verified on
  the deployed site.

- [ ] **R15 — Favicon set and head tags.** Needs: **R8**.
  `favicon.ico`, `favicon.svg`, 48×48 and 96×96 PNGs, `apple-touch-icon.png`
  180×180, `site.webmanifest`, plus the `<link>` tags and `theme-color`.
  Google needs square and ≥48×48; 16/32 alone is browser-tab only.
  Blocked on your logo — the current artwork is drawn corner-to-corner on a
  square canvas, which is why it reads as a hairline at tab size.
  **Done when:** the icon shows in a browser tab and every declared file
  returns 200 on the deployed site.

- [ ] **R16 — SEO and social metadata.** Needs: **R15**.
  Per-page `<title>` and description, `og:*` with a real 1200×630 card,
  `robots.txt`, `sitemap.xml`.
  **Done when:** every route has its own title and description, and the OG card
  renders correctly in a validator.
  **Note:** Search Console submission and reindexing are yours to do and take
  days to weeks. Nothing in code makes Google show a favicon on any timeline.

- [ ] **R17 — Deploy Phase 2 and review.** Needs: **R9–R16**.
  **Done when:** the live site looks finished without the chat existing.
  **Stop here for review.**

---

## Phase 3 — The agent

Needs **R17**. The biggest engineering lift; budget the most time here.

The claim being defended: the policy engine, risk model, entity data and causal
reasoning are deterministic code you own. The model reads your structured data
and talks about it. Your risk tiers never ask an LLM whether something is safe.

- [ ] **R18 — Persistence that survives a cold start.** Needs: **R17**.
  Today every store is in-process; health reports `degraded` and state vanishes
  on a cold start. A chat with no memory between turns is not a chat.
  DynamoDB, single-table, behind the `Store`/`AUDIT` seams that already exist —
  chosen over RDS because its free tier does not expire.
  **Done when:** `/api/v1/health` reports `ok`, and an incident approved before
  a forced cold start is still there afterwards.

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

## Out of scope

From the prompt's own non-goals, repeated because they are the things most
likely to creep in: no multi-tenant SaaS, no billing, no auth beyond what
exists, no fine-tuning or MLOps, no graph database, no SIEM/EDR integrations,
and no describing anything as "autonomous" unless an action actually executed
without a human approving it.
