# Pashupatastra Rebuild — Master Prompt for Claude Code

Paste this whole document into Claude Code, in the root of the pashupatastra repo. It assumes the current live app (Next.js on Vercel, pages: Overview / Incidents / Infrastructure / Actions / Audit, dark mode toggle, one scripted SRE incident) as the starting point.

**Read the whole prompt before writing code. Work through the phases in order — do not jump to Phase 4 with Phase 1 half-done. After each phase, stop and show a summary of what changed before moving on.**

---

## 0. Non-goals (read this first)

Do not attempt any of the following. They are out of scope for this project and will turn a shippable, polished portfolio site into an unfinished mess:

- No multi-tenant SaaS, no billing, no org/auth system beyond what already exists
- No custom-trained ML models, no fine-tuning pipeline, no MLOps stack
- No graph database — a normal relational schema (Postgres) with clean foreign keys is enough to express "threat actor uses malware implements technique"
- No enterprise integrations (SIEM connectors, EDR agents, etc.)
- No claim of being "autonomous" anywhere in copy unless an action actually executed without a human clicking approve — the site already models autonomy tiers correctly, keep that honesty

The goal is one thing done very well: **a live, interactive, cybersecurity-themed incident-response agent demo with a real chat interface, that a recruiter or engineer can play with for five minutes and come away impressed.**

---

## 1. Re-theme the domain: SRE → Cybersecurity Blue Team

### 1.1 Why this is a data-model change, not a copy change

The entity types, action registry, and incident diagnosis text are the domain model. Renaming labels in the UI without changing this underneath will leave the site half-cybersecurity, half-database-outage. Change the actual schema and seed data.

### 1.2 New entity types

Replace `service` / `database` with security-relevant entity kinds:

- `host` (endpoint or server)
- `account` (user or service identity)
- `network_flow` (a connection between two hosts/IPs)
- `asset` (a resource being protected — e.g. a database, an S3 bucket, an app)
- `process` (a running process on a host, optional but nice for detail)

### 1.3 New action registry

Replace the current 13 actions with a security-flavored set. Keep the same risk-tier structure (autonomous / approval required / senior approval / never autonomous) — just repoint the actions and rollbacks:

| Action | Base risk | Rollback | Expected post-state |
|---|---|---|---|
| `read_logs` | 0 | — | — |
| `query_threat_intel` | 0 | — | — |
| `notify_analyst` | 0 | — | — |
| `create_case` | 0 | — | — |
| `require_mfa_reauth` | 10 | `clear_mfa_requirement` | session re-verified |
| `rate_limit_account` | 15 | `remove_rate_limit` | request rate < threshold |
| `force_password_reset` | 20 | — (irreversible-ish, no true rollback) | credential rotated |
| `revoke_session` | 25 | `reissue_session` (requires re-auth) | session invalid |
| `quarantine_email` | 25 | `release_email` | message isolated |
| `block_ip` | 35 | `unblock_ip` | traffic from IP denied |
| `disable_account` | 45 | `enable_account` | account inactive |
| `isolate_host` | 55 | `rejoin_network` | host off network, EDR still reachable |
| `rotate_credentials` | 65 | — | secrets invalidated org-wide for that key |
| `wipe_host` | 100 | irreversible | — |

### 1.4 New scripted incidents (build at least 3, ideally 5)

Each needs the same shape the current incident has: causal chain with evidence IDs, a diagnosis, at least one "also considered" hypothesis that gets contradicted by evidence, a remediation plan with risk-gated actions, and a timeline. Add one new field to every causal-chain step: **`attack_technique`** — a MITRE ATT&CK technique ID (e.g. `T1110.004` for credential stuffing) plus tactic name, shown the same understated way `evidence:` is shown now.

Suggested scenarios, roughly ordered easy → interesting:

1. **Credential stuffing.** Spike in failed logins from a new ASN → one account gets a valid login → new session issued from unfamiliar geo. Diagnosis: credential stuffing succeeded on one account. Alternative considered and contradicted: "user traveling" (contradicted by: impossible-travel evidence, e.g. two logins 4 minutes apart from cities 6,000 miles apart).
2. **Phishing → token theft.** Email with lookalike domain delivered → link clicked (proxy log) → OAuth token issued to unfamiliar app → that token used to read mailbox. Diagnosis: session/token theft via phishing, not password compromise (important distinction — action should be `revoke_session` + `quarantine_email`, not `force_password_reset`).
3. **Lateral movement / beaconing.** Host shows new outbound connection to a rare destination on a regular interval (beacon-like) → same host initiates SMB connections to two other internal hosts it's never talked to before → new scheduled task created on one of them. Diagnosis: possible C2 beacon with lateral movement attempt. Alternative considered and contradicted: "backup job" (contradicted by: destination not in known backup infrastructure list).
4. **Insider / anomalous access.** Service account (normally only ever touches one database) suddenly reads a large volume from a different, sensitive database at 3am local time. Diagnosis: anomalous access pattern, possible credential misuse or insider action. Keep this one low-confidence and explicitly hedge — this is the scenario where the "AI confidence ≠ truth" principle should be most visible.
5. Optional stretch: **data exfiltration.** Large outbound transfer to a personal cloud storage domain right after the anomalous DB read from scenario 4 — chain scenario 4 into this one as a "related incident" to show the memory/correlation angle.

### 1.5 Rewrite the "reading this map" / "why this exists" microcopy

The current site has genuinely good explanatory microcopy (e.g. "a system that hides its own doubt is harder to trust than one that reports it"). Keep that voice. Just make sure every sentence that currently references deploys/services/databases gets rewritten for the security domain — do a full pass, don't leave any SRE language behind by accident.

---

## 2. UI/UX overhaul

Read `/mnt/skills/public/frontend-design/SKILL.md` before touching any component — follow it for type scale, spacing, and color system, and to avoid a generic/templated look.

### 2.1 Fix the known bug

The wordmark in the header renders as "PASHUPASHUPATASTRA" — duplicated text, almost certainly the logo `alt` attribute and adjacent text node both rendering. Find the header/nav component and fix it.

### 2.2 Concrete UI problems to fix

- **Empty states are flat.** "Nothing recorded yet" in Audit and "No activity recorded yet" on Overview are one dull sentence each. Design a real empty state: a small illustration or icon, the explanatory sentence that's already there (it's good), and where relevant a next action ("trigger a demo incident to see this populate").
- **Only one incident exists, ever.** Add a scenario picker — a button or dropdown ("Simulate: Credential stuffing / Phishing / Lateral movement / Insider access") that lets a visitor spin up any of the 3–5 incidents from Section 1.4 on demand. This is the single highest-value UI change: it turns a static screenshot into something people actually click around in.
- **Status iconography is good, keep it, but push contrast and hierarchy further.** The ▲ critical / ◆ degraded / ● healthy / ○ no-data system is smart — make sure color + shape both encode status (not color alone, for accessibility), and check contrast ratios against both the light and dark theme background.
- **No loading or transition states.** Add skeleton states for the incident/infrastructure pages so switching between scenarios feels responsive rather than jumping straight from one static screen to another.
- **Mobile pass.** Check the dependency table and causal chain on a narrow viewport — tables in particular tend to break first.
- **Typography.** Right now it reads as system-default. Pick one deliberate type pairing (a technical monospace for IDs/evidence/risk scores, a clean sans for prose) and apply it consistently — this alone will make the site feel considerably more designed.

### 2.3 Design direction

Lean into the "SOC console" aesthetic the dark mode toggle already implies — but make it feel calm and precise rather than generic "hacker green terminal." Reference points: an air-traffic-control display or a well-designed observability tool (Datadog, Honeycomb) rather than a movie-hacker UI. Muted background, restrained accent color reserved only for status/risk signaling, generous whitespace, monospace for anything that's an ID, score, or evidence tag.

---

## 3. Favicon + browser tab + Google Search branding

This has two separate parts: getting a favicon to show correctly in browser tabs (easy, immediate), and getting it to show in Google Search results (not guaranteed, and slow).

### 3.1 Files to generate and add to `/public`

- `favicon.ico` (multi-size, for legacy browser support)
- `favicon.svg` (scalable, modern browsers prefer this)
- `favicon-48x48.png` and `favicon-96x96.png` — **Google's current guidance is a square favicon at minimum 48×48px**, with larger preferred for sharpness; 16×16/32×32 alone is not enough for Search, only for the browser tab
- `apple-touch-icon.png` (180×180)
- `site.webmanifest` referencing the above, for Android/PWA icon support

### 3.2 `<head>` tags (add to the root layout)

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-48x48.png" sizes="48x48" type="image/png">
<link rel="shortcut icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#0a0a0a">
```

### 3.3 Set real expectations on Google Search

Google requires the favicon file itself and the homepage to be crawlable/indexable, served from a stable (not dynamic) URL, square, and at least 8×8px with 48×48px+ strongly recommended. Even meeting every requirement, Google does not guarantee it will show the favicon, and it can take anywhere from days to a few weeks after a recrawl for it to appear — request reindexing of the homepage via Search Console's URL Inspection tool after deploying, rather than expecting it instantly.

### 3.4 While you're in the `<head>`, also fix SEO/social metadata

- A real `<title>` and `<meta name="description">` per page, not just the site-wide default
- `og:title`, `og:description`, `og:image` (a proper 1200×630 social card, not the tiny favicon) so links look right when shared on LinkedIn/Twitter — worth doing given this is a portfolio piece
- `robots.txt` and a `sitemap.xml`
- Submit the site in Google Search Console if you haven't already — indexing doesn't happen automatically just because it's live on Vercel

---

## 4. Build a real chat interface — and make the agent genuinely yours, not just "Claude in a box"

### 4.1 The distinction that matters

If the whole "AI agent" is just a chat box that forwards your message to Claude with no state of its own, that's fair to call "a Claude wrapper," and it undercuts the "my own AI agent" claim. What makes it actually yours is that **the policy engine, the risk model, the entity/incident data, and the causal-chain reasoning are your own deterministic code — the LLM is only one component, used for natural-language explanation and tool-calling on top of a system you built.** Keep that division explicit and be able to explain it in an interview: your risk-tier logic never asks an LLM "is this safe" — it's fixed rules. The LLM's job is to read your structured data and talk about it, and to call your read-only tools when a user asks a question that needs fresh data.

### 4.2 Architecture

```
User types in chat
        ↓
POST /api/agent/chat  { message, incidentId, conversationHistory }
        ↓
Load incident + causal chain + entity + audit context from your DB
        ↓
Call Claude API with:
  - system prompt describing Pashupatastra's role and boundaries
  - the incident's structured data as context
  - tool definitions for READ-ONLY registered actions only
    (read_logs, query_threat_intel, read the causal chain, read audit history)
        ↓
Claude may call a read-only tool → your API executes it against your DB → returns result → Claude continues
        ↓
If the user asks the agent to DO something (isolate_host, block_ip, etc.):
  the agent may only PROPOSE it — it must go through the existing
  policy engine / approval UI, never execute directly from the chat route
        ↓
Response streamed back to the chat panel
        ↓
Every tool call and every proposal gets written to the audit log,
same as the existing Timeline entries
```

### 4.3 UI for the chat panel

A persistent right-side panel (collapsible on mobile) available on the Incident detail page, seeded with the incident already loaded as context. Suggested starter prompts shown as chips: "Why this diagnosis and not the alternative?", "What's the blast radius if we don't act?", "Walk me through the evidence for step 2", "What would you recommend and why?". Every agent message that references a causal-chain step or evidence ID should link to it, the same way the existing evidence citations work.

### 4.4 Guardrails to actually implement, not just describe

- The chat route only has tool access to read-only registered actions (risk tier 0). It cannot call `isolate_host`, `block_ip`, etc. directly — full stop, enforced in code, not just in the prompt.
- Anything the agent proposes gets created as a pending approval item using the exact same policy/approval flow a human-initiated action would use — no separate, weaker path for AI-initiated actions.
- Log the model, prompt version, and full tool-call trace for every chat turn to the audit table, so "why did the agent say that" is always answerable from the Audit page.

---

## 5. New page: Live Threat Observatory + Blue Team training mode

### 5.1 Real-world feed (use real public data, don't fabricate a "live" feed)

Pull from real public threat intelligence sources and normalize into your own event schema (this reuses the `event ID / source / timestamp / confidence / verification state` structure). Good starting sources with open, machine-readable feeds:

- **CISA Known Exploited Vulnerabilities (KEV) catalog** — actively exploited CVEs, updated regularly
- **abuse.ch feeds** (URLhaus for malicious URLs, ThreatFox for IOCs, MalwareBazaar for samples) — free, well-documented APIs
- **NVD/CVE feed** for vulnerability details to enrich KEV entries

Poll these on a schedule (a Vercel cron job or a scheduled Lambda), normalize into your schema, and store server-side — don't call third-party APIs directly from the browser.

### 5.2 What the page shows

A timeline/map view of real recent entries (what was exploited, what technique/category it maps to, when it was reported, current status) rendered in the same visual language as your incident pages — same evidence-citation style, same verification-state badges (`REPORTED / OBSERVED / CORROBORATED / CONFIRMED`, never mislabel a report as confirmed). Click into an entry to see a plain-language "how this happened, what the impact was, how it's mitigated" writeup, sourced and linked back to the original advisory.

### 5.3 "Trains the agent" — be precise about what this actually means

Be honest with yourself and with anyone you show this to: this does **not** mean continuous model fine-tuning — that's out of scope and not something one person should promise. What it realistically and legitimately means: verified entries from this feed get added to the knowledge base your chat agent retrieves from (Section 4), so when someone asks the agent about a real CVE or technique, it's answering from your own curated, sourced data rather than only the LLM's training data. That's a real, defensible "the agent gets smarter as the observatory grows" story without overclaiming.

### 5.4 Gamified Blue Team mode

This is the most fun part to build and the best teaching tool — and it reuses UI you already have:

1. Pick a scenario (from Section 1.4's incident set, or a real one from the Observatory).
2. Show the player only the first alert — not the full causal chain.
3. At each step, give the player the same options a real analyst has: which entity to investigate next, which read-only action to run (`read_logs`, `query_threat_intel`), and eventually which response action to propose.
4. Score based on: did they reach the correct diagnosis, did they pick a proportionate response (not `wipe_host` for a phishing email), did they avoid the "also considered" red herring.
5. At the end, reveal the full causal chain and ATT&CK mapping as the "answer," with a short explanation of the technique for anyone unfamiliar — this is the actual teaching moment.
6. Keep a lightweight leaderboard/streak if you want a reason for people to come back.

This single page does the most work toward "why should someone bookmark this" of anything in this prompt — it's the difference between a demo and a tool.

---

## 6. Suggested build order

1. **Phase 1** — Section 1 (re-theme data model + 3 scripted incidents) + Section 2.1 (fix the wordmark bug). Get this deployed and look at it before doing anything else.
2. **Phase 2** — Section 2 (full UI/UX pass) + Section 3 (favicon/SEO). Ship a version that looks and feels finished even before the chat exists.
3. **Phase 3** — Section 4 (chat interface + agent architecture). This is the biggest engineering lift — budget the most time here.
4. **Phase 4** — Section 5 (Threat Observatory + Blue Team game mode). Do this last; it's additive and benefits from the incident/action/scoring patterns already being solid from Phases 1–3.

Do not start Phase 3 or 4 until Phase 1 and 2 are actually deployed and reviewed — a half-built chat feature on top of an unfinished re-theme will be harder to debug than doing them in order.
