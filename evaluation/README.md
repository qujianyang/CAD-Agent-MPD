# Evaluation Workspace

The formal local-LLM study is governed by:

- `PROTOCOL.md`: research questions, systems, metrics, and data-separation rules;
- `ENVIRONMENT.md`: verified hardware and runtime inventory; and
- `FREEZE.md`: exact artifacts and settings that must be fixed before final runs.

Files and results created before 2026-07-12 are exploratory. Keep them for the
development history, but do not combine them with frozen confirmatory results.

## Setup

Run commands from the repository root with the project interpreter:

```powershell
.\mpd\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Runner

Check the selected cases without calling a model:

```powershell
.\mpd\Scripts\python.exe -m evaluation.harness.runner `
  --system qwen35_9b `
  --cases evaluation/benchmark/dev.jsonl `
  --repeats 3 `
  --out evaluation/runs/qwen35_9b_dev.jsonl `
  --dry-run
```

Run them by removing `--dry-run`. The runner appends one JSONL record per
case/repeat pair and skips pairs already present in the output file.

Available screening system IDs are:

- `qwen3_14b`
- `qwen35_9b`
- `gemma4_12b`

Each screening config keeps engineering tools enabled and removes
`lookup_knowledge`, giving tools-on/RAG-off conditions.

## Scorer

```powershell
.\mpd\Scripts\python.exe -m evaluation.scoring.scorer `
  --cases evaluation/benchmark/dev.jsonl `
  --runs evaluation/runs/qwen35_9b_dev.jsonl `
  --out evaluation/results/qwen35_9b_dev_scored.json
```

Scoring is deterministic and does not call an LLM judge.

## System D RAG development pilot

The System D configuration pins the selected local RAG artifacts itself:
`bge-m3` through Ollama's native embedding endpoint and
`artifacts/embedding_candidates/bge_m3.json`. It does not rely on a user `.env`
selection. Run the development-only retrieval pilot after `ollama serve` is
available:

```powershell
.\mpd\Scripts\python.exe -m evaluation.harness.runner `
  --system D `
  --cases evaluation/benchmark/rag_dev_pilot.jsonl `
  --repeats 1 `
  --out evaluation/runs/D_rag_dev_pilot_v1.jsonl `
  --max-retries 0
```

The four pilot questions are development data only. Inspect the saved raw JSONL
for `lookup_knowledge` calls and `retrieved_chunk_ids` before building a final
RAG/citation benchmark.

## Safety rule

Do not run or inspect `final.jsonl` until the model, prompt, tool schemas, RAG
index, inference settings, runner, verdict parser, and scorer are frozen in
`FREEZE.md`.
