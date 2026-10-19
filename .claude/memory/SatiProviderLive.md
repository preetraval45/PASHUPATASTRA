# Sati provider live on Lambda

- **Date:** 2026-10-18
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

Production now runs `PASHU_MODEL_PROVIDER=sati`: /agent/ask and /agent/chat answer
from Brahmacharini retrieval over the knowledge base (ATT&CK, CAPEC, CISA KEV). No
external LLM. /health reports `provider: sati`. The page-view counter was failing on
every render because `views` is a DynamoDB reserved word; it now uses a `#views`
placeholder.

## Why

The owner decided that answers come from the project's own models only until
Kushmanda is ready. The first deploy of that change served a stale `dist/api.zip`.

## Decisions made

- Run `scripts/buildlambda.py` before every `deploylambda.py`. Deploy does not
  rebuild the zip, so skipping the build ships whatever zip is already there.
- Write patches with Edit/Write or a Python script, never a bash heredoc. A heredoc
  put `\x08` into the CVE regex, and the Read tool cannot show that character.

## Open questions

- `grounded: false` is reported even when sources are cited. Decide whether
  knowledge-base citations should count as grounded, or whether only incident
  evidence counts.

## Next session should

- Push Kushmanda v1 to Kaggle with a GPU and collect its results.
