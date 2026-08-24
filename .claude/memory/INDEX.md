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
- 2026-08-21 · [Retrieval beats recollection](CuratedIntel.md) — R26: the agent refuses to describe a CVE it has no advisory for
- 2026-08-21 · [Blue team mode](BlueTeam.md) — R27: playing the incident forwards, and two ways to build a game nobody can win
- 2026-08-21 · [A streak, deliberately not a leaderboard](AnonymousProgress.md) — R28: anonymous progress, and the four things that make that structural
- 2026-08-21 · [Phase 4 closed](Phase4Complete.md) — R24–R29 done; five checks that were green while measuring nothing
- 2026-08-24 · [Phase 5 closed](Phase5Complete.md) — R50–R55: the visitor's path, and seven checks that were green while measuring nothing
- [ObservatoryGrouping](ObservatoryGrouping.md) — R56: one row per indicator; why the window is relative to the indicator and not the clock
- [BuildAttribution](BuildAttribution.md) — R57: why the stack belongs on one page and attribution on all of them
- [RealAttackData](RealAttackData.md) — Phase R: real world attacks replace the scripted scenarios; why reported attacks get no causal chain
