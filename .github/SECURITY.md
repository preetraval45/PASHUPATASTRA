# Security policy

Pashupatastra is a platform that proposes and, under policy, takes actions on infrastructure. A
flaw in it can matter more than a flaw in an ordinary website, so reports are welcome and taken
seriously.

## How to report

Use GitHub's private vulnerability reporting:
**[Report a vulnerability](https://github.com/preetraval45/PASHUPATASTRA/security/advisories/new)**.
Only the maintainer sees the report. Please do not open a public issue, pull request or
discussion about an unfixed vulnerability.

Include what you can of:

- what is affected (the website, the API, the Android app, or code in this repository, with the
  path or URL);
- the steps to reproduce, and what you expected instead;
- the impact as you understand it: what an attacker gains;
- whether you have shared it with anyone else.

## What happens next

- An acknowledgement, aiming for within 7 days.
- An assessment, and either a fix or an explanation of why it is not treated as a vulnerability.
- Credit in the fix's advisory, if you want it, once the fix is released.

This is a one-person project, so the times are aims rather than guarantees. There is no paid bug
bounty.

## In scope

- https://pashupatastra.vercel.app and the API it calls.
- The Android app published from this repository's `android` release.
- The code in this repository, in particular anything that lets an action run without a policy
  verdict (rule 2 in [CLAUDE.md](../CLAUDE.md)), a model answer pass without its citations
  (rule 1), or one account or company read or change another's data.

## Out of scope

- Denial of service, load testing or automated scanning that degrades the service.
- Social engineering, phishing or physical attacks.
- Vulnerabilities in third-party services the project runs on (AWS, Vercel, GitHub, Kaggle):
  report those to their owners.
- The Android test build's signing key, which is public by design and documented as test-only.
- Findings without a security impact, such as missing headers with no demonstrated exploit.

## Safe harbour

Research done in good faith within this policy is welcome. Test only against accounts and data
you own, stop and report as soon as you can show the issue, do not keep or share data you reach
by accident, and give a reasonable time to fix it before anything is made public. Do that, and the
project will not pursue or support legal action against you for it.
