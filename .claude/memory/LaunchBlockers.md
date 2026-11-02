# Launch blockers (RP-107): glossary, email verification, company intake, support

- **Date:** 2026-11-02
- **Phase:** Product (RP-107)
- **Commit(s):** 07d9384, 0ad2588, 20c5d1e, f99e280, 8bfeb4c

## What changed

- **Sati gaps:** `concepts.CONCEPTS` gains 31 names, each verified against `knowledge.json` by a test. `concepts.GLOSSARY` holds NIST CSRC definitions quoted verbatim (fetched with curl: WebFetch caps quotes at 125 chars) for terms with no KB entry. The area label is `glossary`, allowed in `general.AREAS` and the schema; before that the live API relabelled it `siddhidatri`.
- **Email verification:** a `verified` field on User; VERIFY tokens are stored hashed with the address, valid 24 h, and resendable once a minute; `/auth/verify`, `/me/verify` and the `/verify` page; fail-soft while SES is off.
- **Company intake:** `pk_` keys stored as a SHA-256 on the org doc; `POST /ingest/{org}` with `X-Pashupatastra-Key`; SIGNAL docs capped at 5,000; `GET /orgs/{org}/signals`; `companysignals.tsx`. Observation only.
- **App support:** More › Report a problem opens a prefilled GitHub issue; Contact support shows only with `-PsupportEmail`.

## Decisions made

- **No near-neighbour mappings for terms the KB lacks** (zero-day, VPN …): a wrong entry is worse than "not found". SIM swapping has neither a KB entry nor a NIST glossary entry, so it stays declined.
- **Company alerts never reach the public audit trail;** only key creation and revocation are recorded.
- **Translation is the owner's call:** which languages, and only the app's own words, because the pages and answers come from English sources.

## Open questions

- CI's api tests failed from 5ad5088 (the peer session's kavach change) on 2 Nov, blocking deploys; reported to that session. Locally all 564 pass.
