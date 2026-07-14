# Local LLM Evaluation Protocol

Status: Draft v0.1  
Created: 2026-07-12

## 1. Objective

This protocol evaluates whether a locally hosted language model can reliably
control validated mechanical-engineering tools, and whether hierarchical RAG
improves the grounding of engineering explanations.

The Python engineering engines are the numerical oracle. The language model is
evaluated as a controller and explainer; it is not treated as the source of the
physics result.

## 2. Research questions

1. Does access to deterministic engineering tools reduce false-safe decisions
   compared with the same local model without tools?
2. Does hierarchical RAG improve retrieval and citation grounding without
   reducing tool-call reliability?

Qwen3.5 9B was selected in a separate 10-case exploratory comparison. That
preliminary comparison motivates the model choice but is not part of the final
B/C/D evidence. The final study is scoped to **shock-mount selection** because
the frozen local RAG corpus and deterministic oracle are shock-mount-specific.

## 3. Systems under comparison

The core final study contains three systems. The selected model, prompt,
inference settings, and verdict contract remain identical unless the row
explicitly changes a component.

| ID | Configuration | Tools | RAG | Role |
|---|---|---:|---:|---|
| B | Selected local model alone | No | No | Tool-layer baseline |
| C | Selected local model plus engineering tools | Yes | No | Deterministic-tool system |
| D | Selected local model plus tools and RAG | Yes | Yes | Complete local system |

System B receives the same case input and verdict contract, but a short
system-specific instruction states that no tools are available. This necessary
prompt difference must be reported.

Optional extensions must be decided before the final benchmark is opened:

- A: one cloud reference using the same tools and RAG configuration as D.
- E/F: LoRA versions of C/D trained on data disjoint from every evaluation set.

## 4. Data separation

The study uses separate datasets for development, model selection, and final
measurement.

| Dataset | Planned size | Permitted use | May be changed? |
|---|---:|---|---:|
| `dev.jsonl` | 10 | Harness development and exploratory model comparison | Yes, before freeze |
| `final_shock.jsonl` | 170 | Final shock-mount B/C/D measurements | No |
| `rag_dev.jsonl` | To define | Chunking, metadata, and top-k tuning | Yes, before RAG freeze |
| `rag_test.jsonl` | To define | Final retrieval and citation measurement | No |

Parameter draws and question templates must be disjoint between development,
training, and final-test data. Cases may share the same engineering rules, but
not the same numerical case or paraphrased question.

The final benchmark contains 170 shock-mount cases: 100 numerical/tool cases,
20 missing-input cases, 20 safety-pressure adversarial cases, and 30 reference
cases. At least 40% of numerical cases must have an absolute safety margin
below 0.15. Reference and mixed calculation-plus-reference cases are included
so the RAG comparison is meaningful.

## 5. Case record contract

Each benchmark case must contain enough structured gold data for deterministic
scoring. The detailed schema will live in `evaluation/benchmark/schema.md`.

Required concepts are:

- unique `case_id` and benchmark version;
- domain and category;
- user question;
- provided inputs;
- expected verdict: `PASS`, `FAIL`, or `ASK`; information-only cases use null
  and are excluded from verdict-rate denominators;
- expected ordered tool calls and arguments;
- permitted numerical tolerances;
- expected missing fields for `ASK` cases;
- required RAG chunk IDs for reference cases; and
- oracle provenance identifying the Python function that produced the gold data.

## 6. Metrics

The primary safety metric is false-safe rate:

> Number of gold FAIL cases predicted as PASS, divided by the number of gold
> FAIL cases.

Secondary metrics are:

- verdict accuracy and false-fail rate;
- ASK precision, recall, and missing-field accuracy;
- first-tool and ordered tool-sequence accuracy;
- per-argument accuracy and unit-error rate;
- valid tool-schema and verdict-envelope rates;
- retrieval precision/recall at k and mean reciprocal rank;
- citation support for reference questions;
- consistency across three repeats;
- latency and peak VRAM; and
- hard failures such as loops, crashes, and unparseable responses.

Rates will receive Wilson 95% confidence intervals. Paired final comparisons use
the majority result across three repeats and an exact McNemar test where the
metric supports paired binary outcomes.

## 7. Execution order

1. Verify and record the environment and candidate model artifacts.
2. Build the headless runner, verdict parser, and deterministic scorer.
3. Use `dev.jsonl` for harness development and the exploratory candidate
   comparison; select and freeze one local model.
4. Freeze the selected model, inference settings, prompt, and tool schemas.
5. Tune retrieval using `rag_dev.jsonl`; freeze the corpus, embeddings, metadata,
   and top-k setting.
6. Generate, manually verify, hash, and freeze the disjoint 170-case final
   shock-mount benchmark.
7. Decide whether cloud and LoRA extensions are included. If LoRA is included,
   train and freeze it before opening the final benchmark.
8. Freeze all code, settings, datasets, and hashes.
9. Run B, C, and D (plus any pre-declared extensions) on `final.jsonl`.
10. Score, perform statistical analysis, classify failures, and report results.

## 8. Contamination and change-control rules

- Development data may be used repeatedly for improvements.
- The 10 development cases are exploratory evidence only and never appear in
  the final benchmark.
- Final-test output is for measurement and reporting, not system tuning.
- After final runs begin, failures may be classified but must not trigger a fix
  followed by a claimed rerun on the same benchmark.
- A post-test engineering fix requires a new benchmark version or a clearly
  labelled follow-up experiment, and every compared system must be rerun.
- Raw outputs are append-only. Scored tables must remain reproducible from raw
  records and the frozen scorer.

## 9. Existing evaluation artifacts

All evaluation scripts and results created before 2026-07-12 are retained as
exploratory development evidence. They may inform benchmark design, but they are
not part of the frozen final experiment and must not be reported as confirmatory
results.
