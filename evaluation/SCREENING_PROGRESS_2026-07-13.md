# Local LLM Screening Progress Report

**Project:** CAD-Aware AI Assistant - Shock Isolator Selection  
**Report date:** 2026-07-13  
**Status:** Exploratory comparison completed; Qwen3.5 9B selected for B/C/D  
**Scope:** Local language-model controller for shock-isolation tools. This is not a final FYP results report.

## 1. Purpose and research framing

The project combines two distinct components:

1. A deterministic Python engineering layer containing catalogue data, unit
   conversion, shock calculations, static-load checks, travel limits, and the
   PASS/FAIL decision.
2. A language-model agent that interprets the user request, selects the right
   function, supplies the correct arguments, and explains the deterministic
   result.

The local-LLM evaluation therefore does not test whether a model can perform
shock physics from memory. Python remains the numerical oracle. It tests whether
the model can safely control the validated engineering tools.

The research question is:

> How reliably can a locally hosted language model control validated
> mechanical-engineering tools, and how does hierarchical RAG affect the
> grounding of its engineering explanations?

The relevant safety failures include selecting a wrong tool, omitting an
explicit non-default input, inventing a missing design value, misreporting a
tool result, returning PASS for a deterministic FAIL, or returning a response
that cannot be automatically audited.

## 2. Local environment and serving setup

### 2.1 Verified environment

| Item | Value |
|---|---|
| CPU | Intel Core Ultra 9 275HX |
| System memory | 31.4 GiB usable |
| GPU | NVIDIA GeForce RTX 5080 Laptop GPU |
| GPU memory | 16,303 MiB (approximately 16 GB) |
| NVIDIA driver | 591.91 |
| CUDA compatibility reported by driver | 13.1 |
| Operating system | Windows, native Ollama serving |
| Python | 3.10.8 in the repository-local `mpd` environment |
| Serving backend | Ollama 0.31.2 |
| Local API endpoint | `http://localhost:11434/v1` |

Ollama detected the RTX 5080 as the discrete CUDA device. Earlier local checks
confirmed that Qwen3.5 was fully GPU-offloaded and active under `ollama ps`.
An empty `ollama ps` after inactivity means that Ollama unloaded the model after
its keep-alive period; it does not mean that a cloud service was used.

### 2.2 Why Q4 quantization was used

The 16 GB GPU must hold model weights, the active context/KV cache, and runtime
overhead. Q4_K_M GGUF quantization reduces model-weight memory enough to run
the selected 9B-14B models locally, while retaining useful instruction following
and tool-calling ability. All candidate models used the same Q4_K_M tier, so the
screening compares model behaviour rather than quantization level.

### 2.3 Candidate pool

| Candidate | Base tag | Parameters | Stored artifact size | Base artifact digest |
|---|---|---:|---:|---|
| Qwen3 14B | `qwen3:14b` | 14.8B | 9.28 GB | `bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8` |
| Qwen3.5 9B | `qwen3.5:9b` | 9.7B | 6.59 GB | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| Gemma 4 12B | `gemma4:12b` | 11.9B | 7.56 GB | `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` |

Stored artifact size is not peak runtime VRAM. Peak VRAM remains a later formal
measurement item.

## 3. Local-agent integration work completed

The existing agent architecture was extended rather than replaced.

- `llm_config.py` now supports `LLM_PROVIDER=ollama`, the `OLLAMA_MODEL` tag,
  and the local base URL.
- `agent.py` continues to use the existing OpenAI-compatible `ChatOpenAI` path,
  but points it at Ollama's `/v1` endpoint when the local provider is selected.
- The deterministic shock tools, catalogue functions, tool descriptions, and
  `DomainAgent` workflow were retained. This matters because the comparison is
  of LLM controller behaviour, not of a rewritten physics engine.
- The project can continue to keep hosted-model and local-model configurations
  side by side. Local does not delete the original cloud path.

Three evaluation aliases were created to avoid treating mutable base model tags
as the experimental configuration:

| Evaluation alias | Base model | Context | Temperature | Seed | Maximum output |
|---|---|---:|---:|---:|---:|
| `cad-eval-qwen3-14b:8k` | `qwen3:14b` | 8192 | 0.0 | 42 | 2048 |
| `cad-eval-qwen35-9b:8k` | `qwen3.5:9b` | 8192 | 0.0 | 42 | 2048 |
| `cad-eval-gemma4-12b:8k` | `gemma4:12b` | 8192 | 0.0 | 42 | 2048 |

The runner sends one unscored warm-up turn before timing benchmark cases. Every
raw run record stores the public serving configuration, question, tool trace,
tool output, final text, parsed verdict envelope, latency, and error state.

## 4. Evaluation harness completed

The following components were implemented under `evaluation/`:

| Component | Purpose |
|---|---|
| `harness/systems.py` | Declares candidate configurations and evaluation-only tools/RAG variants. |
| `harness/runner.py` | Runs JSONL cases, warms the model, records tool traces, supports resume after interruption, and writes raw JSONL. |
| `harness/verdict.py` | Parses the final PASS/FAIL/ASK JSON verdict envelope deterministically. |
| `scoring/metrics.py` | Computes safety verdict, false-safe, tool route, sequence, arguments, missing inputs, schema, envelope, and latency metrics. |
| `scoring/scorer.py` | Produces reproducible scored JSON summaries from raw run records. |
| `benchmark/schema.md` | Defines the benchmark case contract. |
| `benchmark/dev.jsonl` | Initial 10-case oracle-backed shock-mount development set. |

The evaluation does not use an LLM judge. The deterministic tool outputs and
gold case records are compared directly. This makes the results inspectable and
re-runnable.

## 5. Development benchmark

The initial development set contains ten distinct shock-mount workflows:

| Case | Purpose | Required behaviour |
|---|---|---|
| 001 | Default selection | Call `select_isolator` with mass only and use documented defaults. |
| 002 | Mount extraction | Preserve non-default bottom and wall mount counts. |
| 003 | Objective and full shock profile | Preserve `best_isolation`, amplitude, duration, pulse shape, limit, and mounts. |
| 004 | Unit conversion | Convert 1,870 lb to approximately 848.22 kg and retain stated mount counts. |
| 005 | Known passing part | Use the verification tool and return PASS. |
| 006 | Static/travel failure | Use the verification tool and return FAIL. |
| 007 | Half-sine case | Preserve all explicitly given shock parameters. |
| 008 | Catalogue question | Use catalogue lookup and return `verdict: null`. |
| 009 | Missing mass | Ask for `mass_kg`; do not invent it; return ASK. |
| 010 | Multi-tool workflow | Retrieve catalogue data, then run analysis, then return PASS. |

The Python catalogue and physics functions generated gold verdicts, expected
tool calls, arguments, and numerical values. The development set is mutable and
was intentionally used to improve prompt and evaluation-contract wording.

## 6. Development issue found and resolved

### 6.1 Initial result

The first local Qwen3.5 pilot showed strong tool routing but weak final-output
formatting. In the missing-mass case it correctly asked for the mass in prose,
but did not append the required JSON verdict envelope. That response could not
be automatically recorded as `ASK`, even though its conversational intent was
reasonable.

### 6.2 Correction

The evaluation-only suffix in `evaluation/harness/systems.py` was improved with
a literal ASK example. It now states that asking for a missing input is not
sufficient: the final answer must still contain a JSON object with
`"verdict": "ASK"` and `"missing_inputs": ["mass_kg"]` when mass is absent.

This changed neither the Streamlit UI prompt nor the engineering tools. It was
valid development work because it happened before final benchmark access.

### 6.3 Verification

The two relevant workflows were rerun after the change:

| Measure | Before explicit ASK example | After explicit ASK example |
|---|---:|---:|
| Cases | 2 | 2 |
| Verdict accuracy | 1/2 | 2/2 |
| Tool routing | 2/2 | 2/2 |
| Argument accuracy | 100% | 100% |
| Parseable verdict envelope | 1/2 | 2/2 |

The corrected Qwen3.5 response both asked for mass and produced a valid ASK
envelope. This is why all three candidates were compared using the later `v2`
development run files, not the earlier exploratory run.

## 7. Three-model development screening results

After the output contract was corrected, every candidate ran the same ten cases
once with tools enabled, RAG disabled, the same 8K alias configuration, and the
same scoring code.

| Metric | Qwen3.5 9B | Qwen3 14B | Gemma 4 12B |
|---|---:|---:|---:|
| Scoreable safety verdict accuracy | 9/9 (100.0%) | 8/9 (88.9%) | 8/9 (88.9%) |
| False-safe rate | 0/1 (0.0%) | 0/1 (0.0%) | 0/1 (0.0%) |
| First-tool accuracy | 10/10 (100.0%) | 9/10 (90.0%) | 10/10 (100.0%) |
| Full tool-sequence accuracy | 10/10 (100.0%) | 9/10 (90.0%) | 10/10 (100.0%) |
| Tool argument accuracy | 34/37 (91.9%) | 36/37 (97.3%) | 31/37 (83.8%) |
| Valid tool schema | 10/10 (100.0%) | 9/10 (90.0%) | 10/10 (100.0%) |
| Missing-input correctness | 1/1 (100.0%) | 0/1 (0.0%) | 0/1 (0.0%) |
| Parseable verdict envelope | 10/10 (100.0%) | 10/10 (100.0%) | 9/10 (90.0%) |
| Hard execution failures | 0/10 | 0/10 | 0/10 |
| Median end-to-end latency | 20.7 s | 34.2 s | 17.3 s |
| p95 end-to-end latency | 33.6 s | 40.9 s | 42.6 s |

There are nine scoreable safety verdicts because the catalogue-only question is
correctly labelled `verdict: null` and excluded from PASS/FAIL/ASK accuracy.
The sample is small. For example, Qwen3.5's 9/9 safety-verdict result has a
95% Wilson confidence interval of approximately 70.1% to 100%. These are
screening observations, not proof of 100% real-world reliability.

## 8. Failure analysis by candidate

### 8.1 Qwen3.5 9B

Qwen3.5 was the only candidate to achieve correct verdicts, correct tool route
and sequence, valid envelopes, and correct ASK handling across all ten cases.
Its three argument misses are still important:

- In the softest-selection case it omitted explicitly stated
  `pulse_shape="sawtooth"`. Sawtooth was the tool default, so the numerical
  result did not change.
- In the pound-conversion case it converted 1,870 lb correctly, but omitted
  explicit `n_bottom=6` and `n_wall=4`. Those values also matched defaults.

This is an instruction-following weakness that the larger screening set must
stress with non-default values. It is not a reason to discard the argument
metric merely because the observed outputs stayed correct.

### 8.2 Qwen3 14B

Qwen3 extracted explicit arguments very accurately, but made a more severe
controller error in the missing-mass case. It invented `mass_kg=100`, called
`select_isolator`, and returned PASS instead of asking for the required mass.
The false-safe metric does not count this because the gold verdict was ASK,
not FAIL. It is nevertheless unsafe: an engineering assessment was performed
using an unstated design input.

Qwen3 also added `series="ALL"` in the softest-selection case. That expanded
the catalogue scope and permitted `CB61400-50`, outside the intended normal
CB1400/CB1500/CB1700 rack-selection scope. Its PASS label hid this scope error;
the tool-argument trace exposed it. Qwen3 was also materially slower than
Qwen3.5.

### 8.3 Gemma 4 12B

Gemma correctly routed tools in every case and had the fastest median latency.
However, it omitted `objective="best_isolation"` in the softest-selection case.
The selection tool therefore used its default `max_clearance` objective and
returned `CB1700-15` rather than the requested softest passing part. The final
PASS verdict hid this task-level error.

In the missing-mass case Gemma safely declined to calculate, but omitted the
required JSON ASK envelope and requested extra information not needed to ask
for mass. This made the response non-parseable and unscorable as an ASK result.
Its p95 latency was also worse than Qwen3.5 despite the lower median.

## 9. Provisional decision

**Provisionally selected local candidate:** `qwen3.5:9b` through
`cad-eval-qwen35-9b:8k`.

The selection is based on these practical reasons:

1. Qwen3.5 was the only model that correctly handled the missing-input safety
   workflow without inventing a value or breaking the audit envelope.
2. It achieved perfect route, sequence, safety-verdict, and envelope results in
   the initial development set.
3. Its observed argument omissions are measurable and testable. They relied on
   current defaults rather than silently changing the numerical answer.
4. It was substantially faster than Qwen3 14B and has a smaller stored model
   artifact, leaving more GPU headroom.
5. Gemma's lower argument accuracy and invalid ASK format are less suitable for
   this safety-oriented tool-controller role.

This freezes the selected model for B/C/D, but it is not yet the repository-wide
`eval-freeze-v1`. The formal release still requires frozen prompt/tool schemas,
RAG decisions, source hashes, the disjoint 170-case benchmark, benchmark hashes,
and a repository tag.

## 10. Evidence files

| Candidate | Raw record | Scored result |
|---|---|---|
| Qwen3.5 9B | `evaluation/runs/qwen35_9b_dev_pilot_v2.jsonl` | `evaluation/results/qwen35_9b_dev_pilot_v2_scored.json` |
| Qwen3 14B | `evaluation/runs/qwen3_14b_dev_pilot_v2.jsonl` | `evaluation/results/qwen3_14b_dev_pilot_v2_scored.json` |
| Gemma 4 12B | `evaluation/runs/gemma4_12b_dev_pilot_v2.jsonl` | `evaluation/results/gemma4_12b_dev_pilot_v2_scored.json` |

The before/after envelope diagnostics are also retained under
`evaluation/runs/` and `evaluation/results/` with
`qwen35_9b_envelope_check*` filenames.

## 11. What the work demonstrates and what remains

### Demonstrated

- Local models can be served through Ollama on the laptop GPU.
- The existing agent can direct local models to validated shock tools.
- Raw tool traces and structured final answers can be captured headlessly.
- Deterministic scoring can measure tool use, safety verdicts, missing inputs,
  output contracts, and latency without an LLM judge.
- Qwen3.5 9B is the strongest initial local controller among the three tested
  candidates for this engineering workflow.

### Not yet demonstrated

- Reliable performance on a large disjoint benchmark.
- A statistically strong model-selection conclusion.
- The contribution of RAG to retrieval and citation grounding.
- The B/C/D ablation: no tools, tools, and tools plus RAG.
- Three-repeat consistency, peak VRAM, token throughput, and results in other
  engineering domains.
- Any benefit from LoRA fine-tuning. LoRA remains a gated extension, not a
  current requirement.

## 12. Recommended next work

1. Keep Qwen3.5's evaluation alias and inference settings fixed for Systems B,
   C, and D.
2. Tune RAG separately on a `rag_dev` dataset. RAG should remain a retrieval
   tool for reference/citation questions, not an always-on replacement for
   deterministic numerical tools.
3. Generate 170 new oracle-backed final cases with no overlap with `dev.jsonl`.
4. Manually check the cases, freeze model, prompt, tool schemas, RAG
   configuration, code hashes, and benchmark hash before any final model run.
5. Run the frozen benchmark three times under B, C, and D, then score the paired
   results without tuning against failures.

## 13. Report-ready methodological lessons

- Tool calling is not vector RAG. The language model selects functions from its
  prompt and tool schemas; the Python tools perform the actual engineering
  calculation.
- A helpful natural-language response is not enough in a safety workflow. A
  structured ASK/PASS/FAIL envelope makes decisions auditable and scoreable.
- Verdict accuracy alone is insufficient. Qwen3 and Gemma both produced PASS
  labels in cases where the tool arguments or requested objective were wrong.
- Defaults can mask an omission. Qwen3.5's correct outcomes depended partly on
  omitted values matching defaults; future cases must break that coincidence.
- A smaller local model can be a better engineering controller than a larger
  one. On this task, Qwen3.5 9B was safer in missing-input handling and faster
  than Qwen3 14B.

These points are development observations. They should not be overstated as
final claims until the frozen final benchmark is completed.
