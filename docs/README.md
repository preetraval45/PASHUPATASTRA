# Documentation Index

Start here.

## Core

| Document | What it answers |
|----------|-----------------|
| [../README.md](../README.md) | What is Pashupatastra and why does it exist |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system is built and what it deliberately is not |
| [ROADMAP.md](ROADMAP.md) | The 24-week plan of action, phase by phase, with exit criteria |
| [REPOSITORY.md](REPOSITORY.md) | What every directory is for and where new code goes |
| [GLOSSARY.md](GLOSSARY.md) | Every term and subsystem name, defined once |

## Specifications

| Document | What it defines |
|----------|-----------------|
| [specs/Event Model.md](specs/Event%20Model.md) | The normalized event schema every connector emits |
| [specs/Incident Model.md](specs/Incident%20Model.md) | Incident lifecycle, causal chain, and verification records |
| [specs/Policy Model.md](specs/Policy%20Model.md) | Risk scoring, autonomy tiers, and Dharma evaluation |
| [specs/Agent Spec.md](specs/Agent%20Spec.md) | Agent identity, permissions, tools, budget, risk limits |

## Engineering

| Document | What it covers |
|----------|----------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | AWS topology, Vercel/AWS split, IAM model, cost control |
| [SECURITY.md](SECURITY.md) | Threat model, trust boundaries, blast-radius controls |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Workflow, commits, memory protocol, review bar |
| [adr/](adr/) | Architecture decision records |

## Research

| Document | What it covers |
|----------|----------------|
| [research/Paper Outline.md](research/Paper%20Outline.md) | The paper's structure, claims, and contribution |
| [research/METRICS.md](research/METRICS.md) | Metric definitions — how each number is computed |
| [../benchmark/README.md](../benchmark/README.md) | PIB — the incident benchmark |

## Conventions used throughout

- Anything not yet built is marked **Planned**. If a document describes behavior
  that does not exist, it says so in the first line of that section.
- Specifications are versioned (`v0`, `v1`). A breaking change bumps the version
  and gets an ADR.
- Diagrams are ASCII so they survive in git diffs, terminals, and the paper.
