# LlmBaselineRun

- **Date:** 2026-10-18
- **Phase:** Block A — RP-07, RP-08 notes, RP-09 started, RP-10 Claude part
- **Commit(s):** this push

## What changed

- benchmark.yml has an `llm` matrix: naive-llm and pashupatastra-llm ×
  qwen2.5:7b, mistral and llama3. Each job runs Ollama on the runner (CPU),
  with the env PASHU_BASELINE_BASE_URL=http://localhost:11434/v1, plus a kind
  cluster. The `tables` job needs [run, llm] with `if: always()`.
- run.py writes runs-<model_slug>.jsonl for the LLM arms, and every record
  carries model, temperature and hardware. RunRecord gained `model`.
- packages/core/pashupatastra/significance.py provides mcnemar (exact) and
  bootstrap_difference (resampling scenarios), with 7 tests. papertables has
  LLM rows, LLM failure counts and Table 5 for significance.
- The pre-declared matrix is docs/research/experiments/llm-baselines-matrix.md,
  committed in the same push, before any result.
- docs/research/notes/RP-08-pytorch-and-backprop.md is the study guide.

## Why

The owner flagged RP-07 to RP-10 as pending. The Oracle endpoint secrets
don't exist, so the runs use Ollama on GitHub's runners: free, and no secret
needed.

## Gotchas

- Windows bash mangles non-ASCII (— and ·) in heredoc Python. Write patch
  scripts with the Write tool, and set PYTHONIOENCODING=utf-8 before running
  papertables locally.
- Kaggle: this account has no internet in notebooks (not phone-verified), so
  Kushmanda trains from a private dataset `preetraval4518071604/sati-kushmanda-data`
  (code, root docs and cached corpus) via kaggle/kushmanda/offline.py.

## Next session should

- Read the six LLM jobs. If structured output fails on Ollama, llm_error
  counts will be high; fall back to `response_format: {type: json_object}`.
