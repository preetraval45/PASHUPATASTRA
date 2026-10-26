# CI deploys the API (RP-57)

- **Date:** 2026-10-26
- **Phase:** Block G — Product
- **Commit(s):** pending

## What changed

The owner added `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (for the
`Claude` IAM user) as GitHub repository secrets, so CI's `deploy api` job now
deploys on every push to main.

## Decisions made

- The deploy job sets `PASHU_MODEL_PROVIDER: sati`. Without it,
  deploylambda.py finds no third-party key and ships the echo stub,
  replacing the owner's own models live.
- Never use the IAM console password. The owner was told to change it and
  enable MFA, and to deactivate the old key `AKIARZDB…` once the new one
  works.

## Next session should

- If the deploy job fails on permissions, the IAM user needs: Lambda
  get/update on `pashupatastra-api`, `iam:PassRole` on its role, and
  DynamoDB describe/create on the `pashupatastra` table.
