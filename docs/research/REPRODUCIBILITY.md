# Reproducibility

This document says how to regenerate every number this project publishes, and
where each one comes from. It follows the NeurIPS and AAAI reproducibility
checklists. Each item below answers one checklist question.

## The one command

```bash
python scripts/reproduce.py --check
```

This rebuilds every generated table in `docs/research/` from the committed run
records and fails if any committed table differs. It uses the standard library
only and finishes in seconds. Without `--check`, it rewrites the tables in
place.

Training is rerun by GitHub Actions workflows, never by hand. Each workflow
commits its results file, and that file is what the table above is rebuilt
from.

| Result | Workflow · job | Results file | Generated table |
|---|---|---|---|
| Benchmark arms, Tables 1–5 | `benchmark.yml` | `benchmark/results/**/*.jsonl` | [tables.md](tables.md) |
| Katyayani (Sati-RCA) | `train-sati.yml` · `sati-rca` | [models/sati-rca.results.json](models/sati-rca.results.json) | [models/sati-rca.md](models/sati-rca.md) |
| Shailaputri | `train-sati.yml` · `shailaputri` | [models/shailaputri.results.json](models/shailaputri.results.json) | [models/shailaputri.md](models/shailaputri.md) |
| Kalaratri | `train-sati.yml` · `kalaratri` | [models/kalaratri.results.json](models/kalaratri.results.json) | [models/kalaratri.md](models/kalaratri.md) |
| Brahmacharini | `train-sati.yml` · `brahmacharini` | [models/brahmacharini.results.json](models/brahmacharini.results.json) | [models/brahmacharini.md](models/brahmacharini.md) |
| Kushmanda | `kaggle-kushmanda.yml` (Kaggle GPU) | `models/kushmanda.results.json` | `models/kushmanda.md` |

**Known gap.** Benchmark records were kept only as Actions artifacts, which
expire after 90 days, until 18 October 2026. From the next benchmark run
onward, the workflow commits them with the tables. Until that run lands,
`tables.md` cannot be rebuilt from a clean checkout, and `--check` reports it.

## Checklist

**Code.** All training, evaluation and table code is in this repository.
Licences are listed in [LICENSING.md](../../LICENSING.md).

| Area | Location |
|---|---|
| Models | `packages/sati/sati/{rca,detect,loganomaly,embed,lm}/` |
| Benchmark harness | `benchmark/harness/` |
| Table scripts | `scripts/papertables.py` and each model's `report.py` |

There is one runnable notebook per model in `packages/sati/notebooks/models/`.

**Data.** [datasheets.md](datasheets.md) covers every dataset: its source, its
licence, and the exact version or revision used. Two datasets need specific
handling:

- **NAB** is pinned to commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`.
- **LogHub** is licensed for research use only. Its weights are not published,
  but its metrics are.

Every loader downloads from the original source into a cache. No dataset is
redistributed here.

**Splits.** Each split is chosen so that the test cannot leak from training, and
each is stated in the model's card ([models/cards/](models/cards/)):

| Model | Split |
|---|---|
| Katyayani | Leave one system out |
| Shailaputri | Leave one NAB family out |
| Kalaratri | By time, 60/20/20, never shuffled |
| Brahmacharini | By source: groups, tools and campaigns unseen in training |
| Kushmanda (pretraining) | By document, after MinHash deduplication |
| Kushmanda (instruction pairs) | By entity |

Thresholds and epochs are chosen on validation data only. The test split is
read once, at the end. Kapoor and Narayanan (2023) is the leakage checklist
these splits were checked against.

**Seeds.** Every training entry point fixes its seeds to 7: Python `random`,
`torch.manual_seed`, and LightGBM's `seed`. LightGBM runs pin `num_threads` to 2: its `deterministic` mode
is exact only for a fixed thread count, and before this was pinned (26 October
2026) the same code and data trained four different Shailaputri models across
five runs, with F1 moving between 0.382 and 0.424. CPU PyTorch jobs give the
same metrics on rerun. Kushmanda trains on a GPU, where
non-deterministic kernels mean a rerun matches its metrics within noise, not
bit for bit.

**Statistics.**

- Proportions are reported with Wilson 95% intervals.
- Paired arm comparisons use McNemar's exact test.
- Differences in means use a paired bootstrap that resamples whole scenarios
  (`packages/core/pashupatastra/significance.py`).

Every row says how many items it covers. An arm with no records is printed as
an empty row, not left out.

**Baselines.** Each model is compared against a published or standard method on
the same split. Examples:

- PCA (Xu et al. 2009) for Kalaratri;
- BM25 for Brahmacharini;
- the four statistical strategies, scored by the same online harness, for
  Shailaputri;
- the no-learning ranking for Katyayani;
- GPT-2's tokenizer for Kushmanda's.

The external LLMs (Llama 3, Mistral, Qwen 2.5 via Ollama) are benchmark
baselines only ([adr/LLMBaselines](../adr/LLMBaselines.md)). No product path
uses them.

**Compute.** Everything ran on free tiers:

| Workload | Hardware |
|---|---|
| CPU jobs | GitHub-hosted `ubuntu-latest` runners (4 vCPU, 16 GB) |
| Kushmanda | Kaggle's free notebook GPU |

Each results file records the device it ran on, and benchmark records include
the platform and hardware. Every workflow uses Python 3.12. CPU jobs use the
CPU wheel of PyTorch.

**Hyperparameters.** These are stored in each model's code as one config dict
or dataclass and copied into its results file. Nothing was tuned on the test
split.

**Who built it.** The models and this pipeline were designed and written by an
AI assistant (Claude) under the owner's direction
([adr/RealDataModels](../adr/RealDataModels.md)).
