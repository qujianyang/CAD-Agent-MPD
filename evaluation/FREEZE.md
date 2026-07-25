# Evaluation Freeze Record

Status: EVALUATION RELEASE FROZEN (`eval-freeze-v1`)
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
| Serving backend | Ollama, Windows native | 0.31.2 documented for evaluation; 0.32.3 observed at release verification |
| API style | OpenAI-compatible local endpoint | Verified |
| Quantization | Q4_K_M for all three candidates | Verified |
| Model residency policy | One unscored warm-up turn before each runner invocation | Implemented and recorded by runner |

## Main inference settings

These are the intended controlled settings. A setting is not frozen until the
harness proves that Ollama actually receives it.

| Setting | Intended value | Current implementation | Freeze status |
|---|---:|---|---|
| Temperature | 0.0 | Set by evaluation `SystemConfig`, captured in raw records, and verified in client invocation parameters | Frozen |
| Context length | 8192 tokens | Set by evaluation Ollama alias and captured in raw records | Frozen |
| Maximum output tokens | 2048 | Set by evaluation `SystemConfig` and alias; verified in client invocation parameters | Frozen |
| Thinking mode | Disabled for main tool-call study | Request uses `reasoning_effort=none`; verified in client invocation parameters | Frozen |
| Seed | 42 | Set by evaluation `SystemConfig` and alias; captured in raw records | Frozen |
| Tool-call execution | Sequential | Final traces contain zero overlapping tool-call intervals | Verified |
| Repeats | 3 per case | 510 records per system over 170 final cases | Completed |
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
| Final benchmark | `evaluation/benchmark/final_shock_draft_v0.jsonl`, 170 cases, `shock-final-draft-v0.2`, SHA-256 `E27E129A9B6A2750E18D16C007D664B1427BBC715EF743EA0CE5C1ECB13A60ED` | Approved for freeze on 2026-07-14 after review fixes (casing bug, config dedup, boundary recount 40/80, 5 selection-FAIL cases, silent+explicit missing-input mix, 4 adversarial families, reference questions re-pointed to the frozen 34-chunk corpus). |
| Shock model/interface manifest | `evaluation/artifacts/model_interface_manifest.json`, SHA-256 `4946CFDF9386F8C350E76C7313726E30A849D72DA60610D2DF0B2996D0C22A6F` | Rebuilt 2026-07-14 after the engineering-verdict and missing-input guard fixes; scoped to `shock_mount` and Systems B/C/D only. Supersedes `3591F754...A4D1D42`. |
| RAG development qrels | `retrieval_qrels_shock_v1.jsonl`, SHA-256 `012DD835DB59AB0A05832D4024903255CAFFB7CDC2E483D1169717E7E0B6241E` | Updated 2026-07-14: `rag08` repointed from deleted `catalog_overview` to `cb1400_catalog`. Development-only. Superseded hash: `3BC474...1909A1` |
| Selected development RAG index | `bge_m3.json`, SHA-256 `00D972B51D26981FA07DAB64B27A121F6212A4ED781178A304C266FCD49CE528` | Rebuilt 2026-07-14 on the migrated 34-chunk corpus (5 legacy chunks deleted, `road_vibration_check` added). Superseded hash: `B48EA2...AC9C16` |
| Frozen RAG corpus (34 chunks) | `knowledge/shock_mount/`, 34 one-file chunks, IDs = `shock_mount/<stem>` | Corpus migration completed 2026-07-14 (see `docs/shock_rag_corpus_plan.md`); final index freeze recorded above |
| Post-migration retrieval check | `evaluation/results/bge_m3_retrieval_postmigration.json` | 16 in-scope dev queries: Hit@1 0.875 (was 0.8125), Hit@3 1.0, MRR 0.9271 (was 0.9062); scope-boundary query now rank 1 |
| Verdict schema | `evaluation/harness/verdict.py` | Frozen in model/interface manifest |
| Scorer and formal analysis | `evaluation/scoring/` | Frozen with deterministic tests and final outputs |

### Frozen RAG configuration (2026-07-14)

The shock-mount corpus contains 34 one-file Markdown chunks with
stable IDs under `knowledge/shock_mount/`. Three local dense embedding models
were evaluated with identical texts, chunk IDs, metadata filter, exact cosine
search, top-k values (1, 3, 5), hardware, and the 18-query development qrels.

Selected configuration for System D:

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

After corpus migration, results on the 16 in-scope development queries were
Hit@1 87.50%, Hit@3 100.00%, and MRR 0.9271. This was stronger than Qwen3 Embedding 8B (Hit@3
93.75%, MRR 0.8458) and Mixedbread Embed Large v1 (Hit@3 100.00%, MRR
0.7812). Full controls, results, and limitations are recorded in
`evaluation/EMBEDDING_SCREENING_PROGRESS_2026-07-14.md`.

The corpus, index, embedding model, query prefix, retrieval policy, and output
budget are now frozen for System D. Any change requires a new index and a rerun
of the development retrieval evaluation before results can be compared.

System D development pilot: completed on 2026-07-14 using
`evaluation/runs/D_rag_dev_pilot_v3.jsonl`. All four reference cases called
`lookup_knowledge`, returned parseable `verdict: null` envelopes, and used
stable retrieved chunk IDs in citations. This verifies the current local RAG
path; it does not satisfy the final freeze gate until final artifacts and the
disjoint final benchmark are frozen.

### Post-freeze pilot validation (2026-07-14)

The final benchmark and BGE-M3 index were left unchanged while the evaluation
answer contract was corrected and re-manifested. The post-freeze pilots used
development-only cases:

- **B:** three tool-free cases completed with parseable envelopes; it made zero
  tool calls as required by the raw-model baseline.
- **C:** `C_postfreeze_pilot_v3` achieved 3/3 verdict accuracy, 3/3 first-tool
  accuracy, 100% argument accuracy, and 3/3 parseable envelopes. This confirms
  that engineering questions end in `PASS`, `FAIL`, or `ASK`, rather than the
  information-only `null` envelope.
- **D:** `D_postfreeze_rag_pilot_v2` achieved 4/4 first-tool accuracy,
  4/4 parseable envelopes, Retrieval Hit@3 = 4/4, MRR = 1.0, and citation
  recall = 87.5%. The citation shortfall is retained as a measured model result,
  not treated as a pipeline failure.

Core evaluation scope is B/C/D only. Cloud A and LoRA E/F are deferred
extensions and are not included in `eval-freeze-v1`.

## Current source baseline

The shock-mount model/interface manifest is the authoritative source record for
the final study. It captures the complete B/C/D configuration, the local model
alias settings, the shock-mount prompt and tool schema, and all relevant source
file hashes.

| File | SHA-256 on 2026-07-12 |
|---|---|
| `agent.py` | `721902E29BA21A1F230EFBEB13E751296E20E64F5F8B71912B3A32903862E544` |
| `llm_config.py` | `AE65ED7077A837E37ACDF727502E8293DF7310EDA0FEE84991BF8FEF03A1CE98` |

Model/interface canonical content hash: `4946CFDF9386F8C350E76C7313726E30A849D72DA60610D2DF0B2996D0C22A6F`
Model/interface physical file SHA-256: `320BA7D0B7AF061CEF804F6A7CC37008DC6C9C2F94678B3CFD92FF0D99B26297`
Shock prompt SHA-256: `F38C28862C433F65E2E9C480993DBF422D21BA0871CF4F6426950CD37BA7A108`
Shock tool-schema SHA-256: `1C30FA3204B785BF547757A3BFAE2251C901C106A4C0028BC12CE0C2BEFE32A0`
Benchmark version: `shock-final-draft-v0.2`
Benchmark SHA-256: `E27E129A9B6A2750E18D16C007D664B1427BBC715EF743EA0CE5C1ECB13A60ED`
RAG index SHA-256: `00D972B51D26981FA07DAB64B27A121F6212A4ED781178A304C266FCD49CE528`

## Final B/C/D evaluation

The final study completed 170 cases with three repeats for each of Systems B,
C, and D: 510 records per system and 1,530 records overall.

| System | Configuration | Majority verdict accuracy | False-safe rate |
|---|---|---:|---:|
| B | Model only | 38.6% (54/140) | 13.8% (4/29) |
| C | Model plus deterministic tools | 82.1% (115/140) | 13.8% (4/29) |
| D | Model plus tools and frozen RAG | 84.3% (118/140) | 3.4% (1/29) |

The paired B-to-C accuracy increase was 43.6 percentage points with exact
McNemar `p < 0.0001`. The paired C-to-D increase was 2.1 percentage points
with `p = 0.6291`. System D retrieval Hit@3 was 86.7%.

The complete verification record, artifact checksums, clean-environment test,
dataset separation check, operational results, and interpretation limits are
in `evaluation/FINAL_RELEASE_VERIFICATION.md`.

## Release gates for `eval-freeze-v1`

- [x] Repository Python 3.10.8 interpreter and pip are verified from the
      activated user terminal.
- [x] Runtime and development dependencies installed in a fresh Python 3.10.8
      venv. The release-focused suite passed 37/37 tests on 2026-07-26.
- [x] Headless runner, deterministic scorer, formal analysis, benchmark, RAG
      scope, prompt guard, and manifest tests pass in a clean environment.
- [x] Intended inference settings were verified through the Ollama alias,
      direct LangChain invocation parameters, raw run configurations, and tool
      traces. The alias-level presence penalty is overridden to 0.0 per request.
- [x] Prompt and tool schemas pass development cases and are versioned. Verified
      by the 23-test final validation suite and the shock-only interface manifest
      recorded on 2026-07-14.
- [x] One local model is selected from the exploratory comparison and its alias
      digest and inference settings are recorded.
- [x] Development and final cases are disjoint: zero case-ID, exact-question,
      and engineering input-configuration overlaps.
- [x] RAG corpus, embeddings, qrels, metadata filters, and top-k are frozen.
      The 34-chunk BGE-M3 index and its SHA-256 are recorded above.
- [x] Optional cloud and LoRA inclusion decisions are recorded. The core study
      is B/C/D; cloud A and LoRA E/F are deferred extensions.
- [x] Benchmark, source, model, and index hashes are recorded. The benchmark
      and shock-only model/interface manifest were hashed on 2026-07-14.
- [x] A pilot run completes end to end without changing a frozen artifact.
      B, C, and D post-freeze pilots are recorded above.
- [x] This release commit is tagged `eval-freeze-v1`.

## Change control after freeze

Any change to the model weights, quantization, backend, inference settings,
prompt, tool schema, Python engineering engines, RAG index, benchmark, verdict
parser, or scorer invalidates direct comparison with existing final runs. The
change must either start a new evaluation version with all systems rerun or be
reported as a clearly separated follow-up experiment.
