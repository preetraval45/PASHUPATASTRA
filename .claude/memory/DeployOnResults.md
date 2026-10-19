# Deploy after result commits

- **Date:** 2026-10-18
- **Phase:** Block G — Product (RP-57)
- **Commit(s):** pending

## What changed

`ci.yml` now also runs through `workflow_run` when Train Sati models, Benchmark, Train Kushmanda on Kaggle, or World threat data completes on main. Its deploy jobs accept that event.

## Why

Those workflows commit results with GITHUB_TOKEN, and pushes made with that token never trigger another workflow. Vercel's Git integration still redeploys the site on those pushes, but the API on Lambda does not get redeployed. Brahmacharini's served files in `services/api/app/sati_models` would sit on main and never ship.

## Decisions made

- The CI `deploy api` job still does nothing, because the AWS secrets are not set. Lambda was last updated by a manual deploy at 00:45 UTC on 19 Oct, and it matches main's API code.

## Next session should

- Ask the owner to add the AWS secrets, ideally for a scoped deploy role rather than root, so deploys stop depending on a manual run.
