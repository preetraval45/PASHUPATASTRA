# Contributing

## Workflow

1. Branch from `main`.
2. Make the change. Keep the diff scoped to one concern.
3. Write or update the relevant spec in `docs/specs/` **in the same change** —
   a spec that lags the code is worse than no spec.
4. Add an ADR under `docs/adr/` if the change constrains future work.
5. **Write a memory entry** (see below). Required on every push.
6. Open a PR against `main`.

## Commits

Conventional Commits:

```
feat:      new capability
fix:       bug fix
docs:      documentation only
refactor:  no behavior change
test:      tests only
chore:     tooling, deps, scaffolding
```

Scope by subsystem where it helps: `feat(dharma): add novelty penalty`.

## Memory protocol — required on every push

Before pushing, append an entry to `.claude/memory/`:

```
.claude/memory/<Topic>.md    from TEMPLATE.md
.claude/memory/INDEX.md                one-line pointer
```

Record **why**, the decisions made, and what the next session needs to know.
Do not restate the diff — git already has it. The entries that pay off are the
ones capturing rejected alternatives and open questions.

## Architecture Decision Records

Use an ADR when a decision constrains future work: a boundary, a schema, a
dependency, a safety rule. Format: `docs/adr/<Topic>.md`, using
`docs/adr/TEMPLATE.md`. ADRs are immutable — supersede rather than edit.

## Review bar

A change is not mergeable if it:

- Reaches a connector write API without a Dharma verdict
- Adds an action without a risk score, expected post-state, and rollback
- Surfaces a model claim without provenance
- Imports a model vendor SDK outside the AI Gateway
- Parses free text where a structured output belongs
- Skips the audit record

These are the six rules from [../CLAUDE.md](../CLAUDE.md) restated as review
gates. They are checked on every PR because retrofitting any of them later means
rewriting the execution path.

## Style

- Python: typed, Pydantic models at boundaries, `ruff` + `mypy`
- TypeScript: strict mode, no `any` at module boundaries
- Docs: ASCII diagrams, present tense, mark unbuilt things **Planned**
- Naming: subsystem prefixes per [../CLAUDE.md](../CLAUDE.md) — `drishti`,
  `smriti`, `buddhi`, `astra`, `kavach`, `dharma`, `kaal`

## Tests

- Every action needs a rollback test
- Every policy tier needs a denial test
- Every schema needs a round-trip test
- Benchmark scenarios are authored **before** the logic that resolves them
