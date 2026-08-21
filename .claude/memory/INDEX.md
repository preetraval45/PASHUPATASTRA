# Memory Index

One line per push, newest last. Full entries live beside this file, named for
their topic — ordering lives here, not in the filename.

Protocol: before every push, write a topic-named file from
[TEMPLATE.md](TEMPLATE.md) and add its pointer here.

- 2026-08-10 · [Repository foundation](Foundation.md) — scaffold, docs, roadmap; Phase 0 begins.
- 2026-08-10 · [Platform and build](Platform.md) — AWS + Vercel decided; core, API, and dashboard implemented.
- 2026-08-19 · [Demo deployment](DemoDeployment.md) — Vercel + Lambda with no data layer; in-memory fallback and corpus seed.
- 2026-08-19 · [Rebuild Phase 1](RebuildPhase1.md) — R1–R3 done; the 29-task plan and the scope call behind it.
- 2026-08-20 · [Rebuild Phase 1 complete](RebuildPhase1Complete.md) — the demo is a blue-team console; R1–R8 done, Phase A unstarted.
- 2026-08-20 · [Rebuild Phase 2 complete](RebuildPhase2Complete.md) — the demo looks finished; R9–R17 done.
- 2026-08-21 · [Durable state on DynamoDB](DurableState.md) — R18: DynamoDB behind the store seams, and what durability cost when a local run wrote to prod
- 2026-08-21 · [The chat agent, on free model providers](ChatAgent.md) — R19: Groq + Ollama on Oracle, deterministic retrieval, verified citations
- 2026-08-21 · [Sati proposes, Dharma authorises](AgentGuardrails.md) — R20: proposals reach a human; why agent_risk_limit=0 dead-ended them
- 2026-08-21 · [The chat panel, and a verification that lied twice](ChatPanel.md) — R21: Sati on the incident page; how a green check can test nothing
- 2026-08-21 · [Auditing the agent, and a cache that never worked](AgentAudit.md) — R22: why-did-it-say-that provenance; a silent cache miss on every request
- 2026-08-21 · [Real threat intelligence, on a schedule](ThreatFeeds.md) — R24: CISA KEV + URLhaus, cursors, and why intel is never a topology node
