# ApiDeploysFromCI

- **Date:** 2026-10-18
- **Phase:** Block G — RP-57; RP-54, RP-55 and RP-56 confirmed live
- **Commit(s):** this push

## What changed

The `deploy-api` job in ci.yml is gated on the repository secrets
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. It runs buildlambda,
createdynamo and deploylambda (taking the role ARN from the existing
function), then smoke-tests the routes the site needs. `/blue-team` is now a
308 to `/training`, set in next.config.mjs. The page-level redirect it
replaces rendered 200 first.

## Why

Production was weeks stale, and the only deploy path was manual, from a
machine with AWS keys. The owner wants nothing run locally.

## Decisions made

- Access keys go in GitHub secrets for now. SECURITY.md T9 prefers OIDC with
  no static keys, and that can follow once IAM can be changed.
- deploylambda replaces the Lambda environment block, but it carries the model
  key forward. The model is still openai-compat `gpt-oss-20b` (Groq). Per the
  owner, that stays only as baseline and labelled backup until Sati models
  serve.

## Next session should

- Once the owner has added the secrets, push anything and watch `deploy api`.
  If the IAM user lacks Lambda or DynamoDB rights, the "who is deploying" and
  "deploy" steps will show it.
