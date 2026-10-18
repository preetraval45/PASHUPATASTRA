# SatiRcaFirstResults

- **Date:** 2026-10-18
- **Phase:** Block H — RP-58 done; Block G — RP-51 built
- **Commit(s):** a4664c3 (bot results), 7e48da3 (Home), 5dadc94 (ablation)

## What changed

The first real-data run (39166644199) on RCAEval scored as follows.
- Leave-one-system-out: AC@1 88.4% (85.7–90.6), against 57.0% for the
  no-learning baseline, n=645.
- Per held-out system: ob 87.9, ss 95.3, tt 81.9.
- Held-out fault: 89.8%. `loss` is the weakest fault type, at 67.5.
- RE3, never trained on: 80.0% against 48.9%.
- Fault type, end to end: about 57%.

Also: Home got a "Jump in" grid of destinations and a primary call to action.

## Why

The ablation without `n_series` was added because RCAEval roots are always
application services, so the model may be learning "which kind of service"
rather than diagnosing.

## Open questions

- Sati-RCA is infrastructure RCA on microservice metrics. The live site's
  incidents are SECURITY incidents (credential stuffing, phishing, C2),
  because prod runs with ACTION_DOMAIN=security. So Sati-RCA can't answer
  those incidents. Making "all AI our own" on the site needs security models
  (RP-61, UNSW/CIC: research-only licences) and Sati-LM for chat. Tell the
  owner plainly.
- Weight release for the research-only datasets is the owner's decision.

## Next session should

- Read the ablation row in models/sati-rca.md.
- RP-60 to RP-62 detection models, with the same workflow pattern
  (train-sati.yml gets one job per model).
