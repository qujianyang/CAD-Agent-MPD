# Evaluation Freeze Record

Status: SELECTED MODEL FROZEN; FULL EVALUATION FREEZE PENDING  
Draft opened: 2026-07-12

This file becomes authoritative only when every release gate at the end is
checked and the repository is tagged `eval-freeze-v1`. Until then, changes are
allowed only through the development process described in `PROTOCOL.md`.

## Research scope

Primary question:

> How reliably can a locally hosted language model control validated
> mechanical-engineering tools, and how does hierarchical RAG affect the
> grounding of its engineering explanations?

Core final systems: B (model only), C (model plus tools), and D (model plus tools
and RAG). Cloud A and LoRA E/F are optional extensions that must be declared
before final-test access.

## Fixed candidate pool

All candidates use Ollama 0.31.2 and Q4_K_M GGUF weights.

| Candidate | Exact digest |
|---|---|
| `qwen3:14b` | `bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8` |
| `qwen3.5:9b` | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| `gemma4:12b` | `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` |

Selected model: `qwen3.5:9b`, frozen from the 2026-07-13 10-case exploratory
comparison. The preliminary comparison informs model choice; it is not final
reliability evidence. The selected model and inference settings must not change
between Systems B, C, and D.

Frozen evaluation alias: `cad-eval-qwen35-9b:8k`  
Alias digest: `41877dcbd4e07e5c9c40f5ab7968bc651674d83801a171cfd6b0684d13701910`

### Development pilot selection record (2026-07-13)

All three candidates ran the same 10 shock-mount development cases once with
tools enabled, RAG disabled, the evaluation verdict envelope, and the 8K local
aliases. Qwen3.5 9B was selected provisionally because it was the only
candidate with correct safety verdicts (9/9 scoreable), tool route/sequence
(10/10), missing-input ASK handling (1/1), and verdict-envelope parsing
(10/10). Its argument accuracy was 34/37 (91.9%).

The full evidence and failure analysis are in
`evaluation/SCREENING_PROGRESS_2026-07-13.md`. Raw and scored files are
retained under `evaluation/runs/` and `evaluation/results/`.

## Serving and hardware decisions

| Decision | Value | Status |
|---|---|---|
| GPU | RTX 5080 Laptop GPU, 16,303 MiB | Verified |
| Serving backend | Ollama 0.31.2, Windows native | Selected for screening |
| API style | OpenAI-compatible local endpoint | Verified |
| Quantization | Q4_K_M for all three candidates | Verified |
| Model residency policy | Ollama may unload between runs; warm-up must be standardized | Must define in runner |

## Main inference settings

These are the intended controlled settings. A setting is not frozen until the
harness proves that Ollama actually receives it.

| Setting | Intended value | Current implementation | Freeze status |
|---|---:|---|---|
| Temperature | 0.0 | Set by evaluation `SystemConfig` and captured in raw run records | Verified for development aliases |
| Context length | 8192 tokens | Set by evaluation Ollama aliases; observed through Ollama runtime | Verified for development aliases |
| Maximum output tokens | 2048 | Set by evaluation `SystemConfig` and aliases | Verified for development aliases |
| Thinking mode | Disabled for main tool-call study | Evaluation config requests `reasoning_effort=none` | Recorded; model-specific verification remains required before final freeze |
| Seed | 42 where supported | Set by evaluation `SystemConfig` and aliases | Recorded for development aliases |
| Parallel tool calls | Disabled; sequential calls allowed | Explicit only on NVIDIA path | Must implement for local path |
| Repeats | 3 per case | Runner supports configurable repeats; pilot used 1 | Implemented; formal screening pending |
| Chat history | Single-turn benchmark cases | Runner sends `chat_history=None` | Verified |

No supplementary temperature or thinking-mode experiment is part of the core
study. It may be added only as a separately labelled extension.

## Model-selection protocol

- Evidence: exploratory `evaluation/benchmark/dev.jsonl`, 10 cases, one repeat.
- Candidates: Qwen3.5 9B, Qwen3 14B, and Gemma 4 12B.
- Tools enabled and RAG disabled for every candidate.
- Prompt, tool schemas, inference settings, hardware, and backend were identical.
- Qwen3.5 9B was selected for its safety verdicts, missing-input handling,
  tool accuracy, envelope compliance, latency, and smaller runtime footprint.
- These results justify model selection only; they are not reported as final
  system-performance evidence.

## Benchmark and RAG artifacts

| Artifact | Version/hash | Status |
|---|---|---|
| Development cases | `dev-v0.1`, 10 cases | Completed and used for prompt/harness/model development |
| Final benchmark draft | `evaluation/benchmark/final_shock_draft_v0.jsonl`, 170 cases, `shock-final-draft-v0.2` | Regenerated 2026-07-14 after review fixes (casing bug, config dedup, boundary recount 40/80, 5 selection-FAIL cases, silent+explicit missing-input mix, 4 adversarial families, reference questions re-pointed to the frozen 34-chunk corpus). Manual verification and final hash pending |
| RAG development qrels | `retrieval_qrels_shock_v1.jsonl`, SHA-256 `012DD835DB59AB0A05832D4024903255CAFFB7CDC2E483D1169717E7E0B6241E` | Updated 2026-07-14: `rag08` repointed from deleted `catalog_overview` to `cb1400_catalog`. Development-only. Superseded hash: `3BC474...1909A1` |
| Selected development RAG index | `bge_m3.json`, SHA-256 `00D972B51D26981FA07DAB64B27A121F6212A4ED781178A304C266FCD49CE528` | Rebuilt 2026-07-14 on the migrated 34-chunk corpus (5 legacy chunks deleted, `road_vibration_check` added). Superseded hash: `B48EA2...AC9C16` |
| Frozen RAG corpus (34 chunks) | `knowledge/shock_mount/`, 34 one-file chunks, IDs = `shock_mount/<stem>` | Corpus migration completed 2026-07-14 (see `docs/shock_rag_corpus_plan.md`); final index freeze recorded above |
| Post-migration retrieval check | `evaluation/results/bge_m3_retrieval_postmigration.json` | 16 in-scope dev queries: Hit@1 0.875 (was 0.8125), Hit@3 1.0, MRR 0.9271 (was 0.9062); scope-boundary query now rank 1 |
| Verdict schema | `evaluation/harness/verdict.py` | Implemented; final freeze pending |
| Scorer | `evaluation/scoring/` | Implemented; final freeze pending |

### Development RAG selection record (2026-07-14)

The shock-mount development corpus contains 38 one-file Markdown chunks with
stable IDs under `knowledge/shock_mount/`. Three local dense embedding models
were evaluated with identical texts, chunk IDs, metadata filter, exact cosine
search, top-k values (1, 3, 5), hardware, and the 18-query development qrels.

Selected configuration for the System D pilot:

| Setting | Value |
|---|---|
| Embedding provider | Ollama native `/api/embed` endpoint |
| Embedding model | `bge-m3` |
| Index | `artifacts/embedding_candidates/bge_m3.json` |
| Corpus topic filter | `shock_mount` |
| Search | Exact dense cosine similarity |
| Retrieval budget | Top 3 chunks |
| Passage payload budget | First 1,400 characters per retrieved chunk |
| Query prefix | None |

Results on the 16 in-scope development queries were Hit@1 81.25%, Hit@3
100.00%, and MRR 0.9062. This was stronger than Qwen3 Embedding 8B (Hit@3
93.75%, MRR 0.8458) and Mixedbread Embed Large v1 (Hit@3 100.00%, MRR
0.7812). Full controls, results, and limitations are recorded in
`evaluation/EMBEDDING_SCREENING_PROGRESS_2026-07-14.md`.

This is a **development selection**, not the final RAG freeze. Any corpus,
chunking, query-prefix, embedding-model, or retrieval-policy change requires a
new index and a rerun of the development retrieval evaluation before System D
pilot results can be compared.

System D development pilot: completed on 2026-07-14 using
`evaluation/runs/D_rag_dev_pilot_v3.jsonl`. All four reference cases called
`lookup_knowledge`, returned parseable `verdict: null` envelopes, and used
stable retrieved chunk IDs in citations. This verifies the current local RAG
path; it does not satisfy the final freeze gate until final artifacts and the
disjoint final benchmark are frozen.

## Current source baseline

These hashes document the starting point only. They will be replaced after
development and immediately before the freeze tag.

| File | SHA-256 on 2026-07-12 |
|---|---|
| `agent.py` | `721902E29BA21A1F230EFBEB13E751296E20E64F5F8B71912B3A32903862E544` |
| `llm_config.py` | `AE65ED7077A837E37ACDF727502E8293DF7310EDA0FEE84991BF8FEF03A1CE98` |

Prompt version: `PENDING`  
Tool-schema version: `PENDING`  
Benchmark version: `PENDING`  
RAG index version: `PENDING`

## Release gates for `eval-freeze-v1`

- [x] Repository Python 3.10.8 interpreter and pip are verified from the
      activated user terminal.
- [ ] Runtime and development dependency files are confirmed reproducible from a
      clean environment.
- [x] Headless runner and deterministic scorer pass their offline tests (12
      harness tests plus 24 related agent/provider regressions on 2026-07-12).
- [ ] All intended inference settings are visible in a captured Ollama request or
      verified by an equivalent controlled check.
- [ ] Prompt and tool schemas pass development cases and are versioned.
- [x] One local model is selected from the exploratory comparison and its alias
      digest and inference settings are recorded.
- [ ] Development and final cases are disjoint and manually checked.
- [ ] RAG corpus, embeddings, qrels, metadata filters, and top-k are frozen.
- [ ] Optional cloud and LoRA inclusion decisions are recorded.
- [ ] Benchmark, source, model, and index hashes are recorded.
- [ ] A pilot run completes end to end without changing a frozen artifact.
- [ ] Git tag `eval-freeze-v1` is created.

## Change control after freeze

Any change to the model weights, quantization, backend, inference settings,
prompt, tool schema, Python engineering engines, RAG index, benchmark, verdict
parser, or scorer invalidates direct comparison with existing final runs. The
change must either start a new evaluation version with all systems rerun or be
reported as a clearly separated follow-up experiment.
