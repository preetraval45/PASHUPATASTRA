# Accounts, companies and training records

- **Status:** accepted, 1 November 2026
- **Decided by:** the owner ("I want this to be a product I can sell as a service … they can track their employees … guest login and Google login"), with these constraints: no paid domain yet, and Sati's own models only, with no third-party AI.

## Context

Until now the site held no personal data. Training progress lived in the browser, and the Blue Team game used an anonymous token that was deliberately unable to carry a name (`services/api/app/progress.py`). Selling to companies needs one thing that design cannot do: a company admin seeing which employees finished their training.

## Decision

Add optional accounts (`services/api/app/accounts.py`, `api/accountroutes.py`), with the least data that feature needs.

- **Sign-in:** guest (an id only), email and password (scrypt hash), and Google through Google Identity Services. The browser gets a Google ID token, and the API asks Google's tokeninfo endpoint to verify it and checks the audience. Only the public client ID is configured (GitHub variable `GOOGLE_CLIENT_ID` → `PASHU_GOOGLE_CLIENT_ID`); no Google secret exists. Apple sign-in waits for a domain.
- **Sessions:** HMAC-signed tokens with a 30-day expiry. The key is `PASHU_AUTH_SECRET` when set; otherwise one is made once and kept in the store.
- **Companies:**
  - roles: owner, admin, employee;
  - joining with an 8-character invite code that admins can rotate;
  - admins see members' names, emails, levels passed, best scores and last activity.
- **Training records:** best score kept and passes never undone. Scores are marked in the browser, so they are self-reported. The dashboard and the privacy notice say so: a training record, not a supervised exam.
- **Privacy:**
  - nothing about an account enters the public audit trail;
  - no IP or device data is stored with an account;
  - `DELETE /me` erases the account, its sign-in keys, memberships and training;
  - `/privacy` was updated in the same change.
- **Storage:** documents in the existing DynamoDB table (partitions USER, LOGIN, ORG, MEMBER, MEMBEROF, INVITE, TRAINING), or memory when there is no durable store. Postgres has no document methods yet, so an on-prem Postgres deployment keeps accounts in memory until it gains them.

## Consequences

- API Gateway and the Function URL must allow the `Authorization` header and the PUT, PATCH and DELETE methods (`scripts/deployapigateway.py`, `scripts/deploylambda.py`).
- **Self-reported scores:** a company that needs proctored certification needs server-marked tests. That means moving module quizzes into the API and marking answers there, as `progress.py` already does for the game.
- **Rate limiting:** ten wrong passwords for one email in 15 minutes lock it for the rest of that window. Email verification is not built yet and should land before the product is sold.
