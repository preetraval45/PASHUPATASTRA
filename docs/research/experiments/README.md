# Paper experiments, 7 October 2026

The scripts and raw records behind RQ2 to RQ4 (Tables VIII to X) of
`../Pashupatastra IEEE Paper.docx`. Every number the paper reports for these
experiments is recomputed from the JSON here by `analyse.py`; nothing was
transcribed by hand.

| Script | What it measures | Needs |
|---|---|---|
| `pibpolicy.py` | Dharma's tier for every expected, allowed and forbidden action in all 104 PIB scenarios, under three contexts | nothing |
| `compromised.py` | What an attacker who controls every byte of the model output can cause through `POST /agent/chat` | nothing (scripted provider) |
| `injection.py` | Indirect prompt injection against real local models through `POST /agent/chat` | Ollama with the model pulled |
| `analyse.py` | Turns `res-*.json` into the per-model figures | nothing |

## Rerun

From `services/api`, with the repository virtualenv:

```
python ../../docs/research/experiments/pibpolicy.py ../../benchmark/incidents/pib pibpolicy.json
python ../../docs/research/experiments/compromised.py compromised.json
python ../../docs/research/experiments/injection.py qwen2.5:7b 3 res-qwen.json
python ../../docs/research/experiments/analyse.py res-*.json
```

`injection.py` and `compromised.py` set their own `PASHU_*` environment and
refuse to run against DynamoDB or Postgres: they seed the in-memory demo store.

## What these do not measure

- **Diagnosis accuracy.** The demo incidents hand the agent their stored
  hypotheses as evidence, so the "diagnosis" question in `injection.py` checks
  citation faithfulness only. A real diagnosis measure needs the PIB stack
  running, because only injected faults produce telemetry that does not name
  its own cause.
- **Adaptive attacks.** The eight payloads are fixed, written in advance.
- **The cluster benchmark.** Table VII in the paper comes from runs whose
  records are not in this repository (`benchmark/results/` is gitignored).

Hardware for the recorded run: one NVIDIA RTX 5070 Ti, Ollama 0.40.0, models
`qwen2.5:7b`, `mistral:latest` (7B), `llama3:latest` (8B).
