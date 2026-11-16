# Lighthouse (generated)

Generated 2026-11-16 15:51 UTC by the `lighthouse` workflow from 12 reports against the production site. Lab data from one GitHub runner with Lighthouse's throttling; compare runs and pages with each other. Do not edit by hand.

| Page | Form | Perf | A11y | Best practices | SEO | FCP | LCP | TBT | CLS | Speed Index | Weight |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `/ask` | desktop | 100 | 97 | 100 | 100 | 0.3 s | 0.6 s | 0 ms | 0.002 | 0.5 s | 482 KB |
| `/ask` | mobile | 91 | 93 | 100 | 100 | 1.3 s | 3.2 s | 180 ms | 0 | 1.4 s | 469 KB |
| `/` | desktop | 99 | 97 | 100 | 100 | 0.3 s | 0.5 s | 0 ms | 0 | 1.3 s | 418 KB |
| `/` | mobile | 79 | 96 | 100 | 100 | 1.2 s | 2.7 s | 360 ms | 0.001 | 9.3 s | 407 KB |
| `/incidents` | desktop | 99 | 96 | 100 | 100 | 0.3 s | 0.7 s | 0 ms | 0.053 | 0.7 s | 593 KB |
| `/incidents` | mobile | 87 | 96 | 100 | 100 | 1.1 s | 3.1 s | 230 ms | 0 | 4.5 s | 577 KB |
| `/incidents/LIVE-C2-stealc-20261116` | desktop | 99 | 96 | 100 | 100 | 0.3 s | 0.6 s | 0 ms | 0 | 1.1 s | 484 KB |
| `/incidents/LIVE-C2-stealc-20261116` | mobile | 93 | 96 | 100 | 100 | 1.1 s | 3.1 s | 130 ms | 0 | 2.1 s | 459 KB |
| `/overview` | desktop | 100 | 96 | 100 | 100 | 0.3 s | 0.5 s | 0 ms | 0 | 0.4 s | 418 KB |
| `/overview` | mobile | 95 | 96 | 100 | 100 | 1.0 s | 2.5 s | 180 ms | 0 | 1.2 s | 406 KB |
| `/training` | desktop | 100 | 97 | 100 | 100 | 0.4 s | 0.7 s | 0 ms | 0 | 0.6 s | 443 KB |
| `/training` | mobile | 95 | 96 | 100 | 100 | 1.1 s | 3.0 s | 50 ms | 0 | 1.3 s | 430 KB |

## Largest opportunities (estimated LCP saving ≥ 300 ms)

- Document request latency — up to 1.9 s on `/` (mobile)
- Largest Contentful Paint element — up to 0.7 s on `/ask` (mobile)
- Improve image delivery — up to 0.5 s on `/training` (mobile)
