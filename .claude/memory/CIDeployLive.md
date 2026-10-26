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

## Result

CI run 40393376125 deployed live: `/health` reports provider `sati` and every
route returns 200. RP-57 is ticked. The first live answer showed CAPEC
`<xhtml:p>` markup; `embed/data.clean` and the provider's `first_sentences`
now strip tags. The knowledge base regenerates clean on the next
Brahmacharini run.
