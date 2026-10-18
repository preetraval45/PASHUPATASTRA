# OpenCoreLicence

- **Date:** 2026-10-18
- **Phase:** Research plan, Block A — RP-04 and RP-31 closed
- **Commit(s):** this push

## What changed

The owner decided: keep the four Sati model names, release weights publicly
under Apache-2.0, and use RCAEval as the external benchmark. LICENSE files
were added to packages/core, packages/sati, packages/sdk and benchmark/, with
a root LICENSING.md table. Both ADRs are now Accepted. CLAUDE.md and
GLOSSARY.md define "Sati models".

## Why

The owner first picked "Apache-2.0" for weights and code. Claude stopped to ask
about scope before adding a licence file, because the README says the cloud
platform is commercial, and Apache-2.0 can't be withdrawn once published. The
owner chose open core only.

## Decisions made

- Root file is LICENSING.md, not LICENSE. A root LICENSE would make GitHub
  label the whole repository Apache-2.0, which is not true.
- The logo is explicitly excluded, because its provenance is unestablished
  (BRAND.md).
- packages/connectors is not in the open set. The owner's option listed
  core/sati/sdk/benchmark only, although backlog 6.2 lists connectors for the
  split. Decide it at the split.

## Next session should

- RP-32: the RCAEval adapter and pre-declared subset (RE2), on GitHub Actions,
  not locally.
- R108 (Zenodo DOI) was blocked on a licence. It is now unblocked for the open
  core.
