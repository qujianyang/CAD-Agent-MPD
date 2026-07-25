# Current Status

_Last updated: 2026-07-26 (formal B/C/D evaluation completed and frozen)_

## Formal evaluation release (2026-07-26)

- Completed the shock-mount B/C/D controlled ablation on the frozen 170-case
  benchmark with three repeats: 510 records per system, 1,530 total.
- Majority verdict accuracy: B 38.6% (54/140), C 82.1% (115/140), and D 84.3%
  (118/140).
- False-safe rate: B 13.8% (4/29), C 13.8% (4/29), and D 3.4% (1/29).
- Paired exact McNemar results: B to C +43.6 percentage points, `p < 0.0001`;
  C to D +2.1 points, `p = 0.6291`.
- System D retrieval Hit@3 was 86.7%. RAG produced a measurable safety gain,
  but its small overall verdict-accuracy increase was not statistically
  significant in this benchmark.
- Preserved raw B/C/D records, deterministic scored files, formal JSON, and
  the report under `evaluation/runs/` and `evaluation/results/`.
- Clean-room reproducibility check passed: fresh Python 3.10.8 venv installed
  from `requirements-dev.txt`; release-focused suite passed 37/37 tests.
- Verified development/final separation: zero case-ID, exact-question, or input
  configuration overlaps.
- Authoritative closeout:
  `evaluation/FINAL_RELEASE_VERIFICATION.md` and `evaluation/FREEZE.md`.
- Release tag: `eval-freeze-v1`. Any model, prompt, tool, engine, RAG, benchmark,
  parser, or scorer change starts a new evaluation version.

## Local RAG development checkpoint (2026-07-14)

- Built a 38-chunk shock-mount-only corpus from `knowledge/shock_mount/` and
  compared three local dense Ollama embedders on 18 development qrels.
- Selected `bge-m3`: Hit@1 81.25%, Hit@3 100%, MRR 0.9062 across 16 in-scope
  queries. Evidence: `evaluation/EMBEDDING_SCREENING_PROGRESS_2026-07-14.md`.
- System D now pins the selected BGE index
  `artifacts/embedding_candidates/bge_m3.json`, local embedding endpoint, and
  1,400-character-per-passage RAG output budget in `evaluation/harness/systems.py`.
- `D_rag_dev_pilot_v3.jsonl` passed 4/4 development reference cases: one RAG
  tool call each, required grounding present, parseable information-only
  envelopes, and stable chunk-ID citations. Earlier v1/v2 failures are retained
  as development evidence; v3 fixed output-format and context-budget issues.
- Next: generate, validate, hash, and freeze the disjoint final benchmark. Do
  not change selected model, embedding model, index, prompt, tools, or scorer
  once final runs begin.
- Generated `evaluation/benchmark/final_shock_draft_v0.jsonl`: 170
  shock-mount-only draft cases (100 numerical/tool, 20 missing-input, 20
  safety-pressure adversarial, 30 reference). It has 75 PASS, 25 FAIL, 40 ASK,
  30 information-only verdicts, and 46 boundary-band numerical cases. It is
  not frozen: manual case review and a final hash are still required.

## Local-LLM screening checkpoint (2026-07-13)

- Implemented and used the local Ollama evaluation path with controlled 8K
  aliases: `cad-eval-qwen3-14b:8k`, `cad-eval-qwen35-9b:8k`, and
  `cad-eval-gemma4-12b:8k`. Main development settings: temperature 0, maximum
  output 2048, seed 42, no RAG, tools enabled, single-turn cases, warm-up turn
  unscored.
- `evaluation/benchmark/dev.jsonl` now contains a 10-case oracle-backed
  shock-mount development pilot. It covers defaults, non-default mounts,
  objective extraction, pound conversion, PASS/FAIL verification, half-sine,
  catalogue lookup, missing input, and a two-tool workflow.
- Enhanced the evaluation-only verdict prompt in `evaluation/harness/systems.py`
  with an explicit ASK JSON example after Qwen3.5 initially omitted the envelope
  on missing-input responses. Production/UI prompting was not changed.
- Full v2 development pilot results, one repeat each:
  - Qwen3.5 9B: safety verdict 9/9, first tool 10/10, arguments 34/37 (91.9%),
    envelope 10/10, missing input 1/1, p50 20.7 s, p95 33.6 s.
  - Qwen3 14B: safety verdict 8/9, first tool 9/10, arguments 36/37 (97.3%),
    envelope 10/10, missing input 0/1, p50 34.2 s, p95 40.9 s. It invented
    mass_kg=100 when mass was missing and broadened scope with series=ALL.
  - Gemma 4 12B: safety verdict 8/9, first tool 10/10, arguments 31/37 (83.8%),
    envelope 9/10, missing input 0/1, p50 17.3 s, p95 42.6 s. It omitted the
    best-isolation objective and failed the ASK envelope.
- User selected and froze Qwen3.5 9B for B/C/D based on the exploratory 10-case
  comparison. The 40-case screening stage was removed from the streamlined
  protocol. This is not yet `eval-freeze-v1`: RAG tuning/freeze, final source
  hashes, and the disjoint 170-case final benchmark remain pending.
- Detailed report: `evaluation/SCREENING_PROGRESS_2026-07-13.md`.

Next local-LLM task: define and generate the disjoint 170-case final benchmark,
while keeping Qwen3.5 and its inference settings fixed. RAG cases cannot be
fully frozen until the corpus/index and stable chunk IDs are frozen.

## Local-LLM evaluation checkpoint (2026-07-12)

- Added `evaluation/PROTOCOL.md`, `ENVIRONMENT.md`, and `FREEZE.md` as the new
  authoritative protocol. Existing pre-2026-07-12 evaluation outputs are
  exploratory only.
- Core final comparison is B/C/D: selected local model alone, plus deterministic
  tools, then plus RAG. Cloud and LoRA are optional extensions decided before
  final-test access.
- Candidate screening pool is installed in Ollama 0.31.2, all Q4_K_M:
  `qwen3:14b`, `qwen3.5:9b`, and `gemma4:12b`. Exact digests are in `FREEZE.md`.
- Verified current laptop runtime: Python 3.10.8 in repo-local `mpd`, pip 26.1.2,
  RTX 5080 Laptop GPU (16,303 MiB), NVIDIA driver 591.91 / CUDA 13.1.
- Implemented the Phase 1 headless foundation:
  - `evaluation/harness/systems.py`: candidate registry and tools/RAG variants.
  - `evaluation/harness/runner.py`: resume-safe JSONL runner and tool traces.
  - `evaluation/harness/verdict.py`: strict PASS/FAIL/ASK JSON parser.
  - `evaluation/scoring/metrics.py` + `scorer.py`: deterministic core metrics,
    Wilson intervals, consistency, latency, and false-safe measurement.
  - `evaluation/benchmark/schema.md`: benchmark JSONL contract.
  - `requirements-dev.txt`: pinned pytest dependency.
- Verification: 12 harness tests passed; 24 related provider/agent/guard/history
  regressions passed. Runner and scorer CLIs load successfully.
- Formal model runs have NOT started. Before screening, the code must enforce and
  verify temperature 0, context 8192, max output 2048, thinking off, seed 42 where
  supported, and sequential tool calls. These gaps are tracked in `FREEZE.md`.
- Next task: create the 20-case development set, beginning with a 10-case
  shock-mount pilot whose gold tools/arguments/verdicts come from Python oracles.

_Last updated: 2026-07-08 (custom isolator backend + agent tool + Streamlit custom vendor UI)_

## Latest session notes (2026-07-08)

- Direction agreed for scalable vendor support: keep the existing shock physics engine vendor-agnostic, and add a deterministic backend normalization layer before it.
- Core boundary: LLM decides workflow and explains results; Python owns validation, unit conversion, stiffness derivation, physics, and pass/fail.
- Target backend shape:
  - Vendor/user data enters as raw vendor-specific inputs.
  - Backend validates required compression + shear data.
  - Backend normalizes to `IsolatorSpec(k_comp_Nm, k_shear_Nm, d_max_comp_mm, d_max_shear_mm, max_static_comp_daN)`.
  - Existing `run_analysis` / `select_and_analyze` remain unchanged.
- Supported stiffness input modes for first backend slice:
  - Direct stiffness K, e.g. VMC/Helical CB data in lb/in or N/mm.
  - Rated load at natural frequency, e.g. Vibratec `30 kg @ 10 Hz`; derive `K = m * (2*pi*f)^2` and mark `screening_only`.
  - Shock force at shock deflection, e.g. Socitec `Max Shock F daN` with `d mm`; derive `K = F / d` and mark as derived shock load-deflection.
- Socitec CB1400 PDF was inspected. It appears physically close to current CB1400 data and provides shock load-deflection pairs, so it fits the backend adapter approach better than Vibratec for shock screening.
- UI decision: do backend first, not a universal UI form. A form/upload should become a thin wrapper after the backend contract is stable.
- Backend first slice implemented:
  - Added `custom_isolator.py` with `CustomIsolatorInput`, `DirectionInput`, `StiffnessInput`, `normalize_custom_isolator`, and `NormalizedCustomIsolator`.
  - Added `tests/test_custom_isolator.py` covering VMC direct K, Vibratec rated-load/frequency K derivation, Socitec shock force/deflection K derivation, missing shear rejection, and invalid unit/frequency rejection.
  - Verification: `tests/test_custom_isolator.py` passed (`5 passed`); relevant shock regressions `tests/test_shock_static_gate.py tests/test_impulse_validity.py tests/test_shock_tools.py` passed (`30 passed`).
- Backend analysis wrapper implemented:
  - Added `custom_isolator_analysis.py` with `analyze_custom_isolator`, returning `CustomIsolatorAnalysis`.
  - Wrapper runs normalization, existing `run_analysis`, explicit static-gate status, combined warnings, `validation_level`, and `PASS`/`FAIL` verdict.
  - Added `tests/test_custom_isolator_analysis.py` covering VMC validated pass, Vibratec static fail + screening warning, Socitec shock-load/deflection screening, missing shear rejection, and bad mass/mount count rejection.
  - Verification: custom isolator tests passed together (`10 passed`); relevant shock regressions passed (`30 passed`).
- Agent custom-isolator tool implemented:
  - Added `analyze_custom_isolator` LangChain tool in `agent.py` with flat scalar parameters for custom/vendor rows.
  - Tool supports `direct_k`, `rated_load_frequency`, and `force_deflection` stiffness modes for compression and shear, then delegates all validation/conversion/physics to backend modules.
  - Registered in `_SHOCK_TOOLS`, documented in `SHOCK_CAPABILITIES`, and added to the tool-use guard/prompt.
  - Verification: `tests/test_shock_tools.py tests/test_build_agent.py` passed (`27 passed`); backend custom-isolator tests passed (`10 passed`); shock regressions passed (`33 passed`).
- Streamlit Quick Selector custom-vendor mode implemented:
  - Added `Custom vendor data` mode beside Auto and Manual.
  - UI captures vendor/part, compression and shear stiffness source, travel, optional static rating, and existing mass/mount/shock/clearance inputs.
  - Supported input sources match backend: direct K, rated load @ frequency, and shock force @ deflection.
  - The button runs `analyze_custom_isolator`, renders validation level/provenance warnings, static gate, derived K values, and the same 4-case physics report.
  - No Excel/file upload yet by design; upload should later pre-fill this same backend contract.

_Last updated: 2026-05-25 (end of long session, just before compact)_

## What works (end-to-end)

- 3-tab Streamlit app: Quick Selector / CAD + Shock / Agent Chat
- Live SolidWorks extraction with `--file` arg or active-doc resolution
- CG extraction via Path A (commercial license) **or** Path B (bbox fallback for Education Edition)
- 7-tool LangChain agent with streaming tool-call visibility in the UI
- Hierarchical RAG over `knowledge/shock_mount/` (4 `.md` chunks)
- Physics matches Excel to 4 d.p. for the CB1400-15 / 850 kg / 6+4 case (GT=6.296 G, ΔD=18.85 mm)
- Anti-hallucination: pulse duration is model-facing as `to_ms` (ms), converted to SI seconds inside the tool — fixes the `0.011 -> 0` truncation; runtime clamp + NOTE injection kept as backstop
- History cap: stateful engineering assistants (shock/tiedown/mobility) feed only the last `_MAX_HISTORY_TURNS` (3) turns to the LLM via `_limit_history` in `DomainAgent.stream()`; UI transcript/export unaffected
- CB61400 opt-in: assistant `select_isolator`/`filter_by_deflection` default `series="AUTO"` → `AUTO_SELECT_CATALOGS` (CB1400/CB1500/CB1700, excludes the soft 6-strand CB61400). `series="ALL"` or `"CB61400"` re-includes it; `get_isolator_data` still lists it. Mirrors the UI selector default.

## Test status

Tier 1-6 chatbot accuracy benchmark:
- **Run 1**: 10 / 12 evaluable passing
- **Run 2** (after adding `find_capacity_limit` + `filter_by_deflection`): **14 / 16 evaluable passing**

## What's not done

- **Phase 1 — Combined CG Calculator** (the boss's original ask). Still skipped. May matter if the boss pushes for it.
- Last PR was created **before** the following changes landed. **Many uncommitted changes:**
  - Streaming UI (st.status, _render_trace)
  - CAD file-path picker (radio: active doc vs specify path)
  - `find_capacity_limit` tool
  - `filter_by_deflection` tool
  - App error-display (red banner + stderr expander)
  - CG extraction fix (Path A + Path B fallback)

## FYP report — where this left off

Structure agreed for **"Problem in Research Aspects"** (4 sections, balanced between mech eng and AI/RAG):

1. **§3 Methodology** — Physics methodology (4 equations + load distribution + selection + binary search) + AI/RAG methodology (architecture + 7 tools + hierarchical RAG + cosine similarity + safety nets) + Integration
2. **§2 Literature Review** — Parallel tracks: (Harris & Piersol / Tinker & Cutchins / MIL-STD-810H / VMC catalog) ∥ (Vaswani 2017 / Touvron 2023 / Lewis 2020 / Yao 2022 / Schick 2023 / Ji 2023) → Research Gap paragraph
3. **§4 Data Validation** — Physics 4-dp match table, RAG hallucination tests (3/3), citation tests (3/3), CAD extraction match (mass/bbox/CG)
4. **§5 Performance Benchmarks** — Latencies table, Tier 1-6 Run 1 vs Run 2 (10/12 → 14/16), scalability & extensibility table

User was offered options A-E for which section to draft fully:
- A. Full §3 Methodology
- B. Full §4 Data Validation
- C. Full §5 Performance Benchmarks
- D. Just the polished Research Gap paragraph
- E. All four sections (~10–12 pages)

**User did not select before the session ended.** When the next session starts, **ask which one** before drafting.

## Likely next asks

- "Draft section X of the FYP report" (A–E above)
- "Should I rename the project / reframe the scope?" (CAD is thin — consider adding a second domain like generator sizing, or repositioning as trustworthy-AI research)
- "Help me commit / open a PR for all the changes since last PR"
- "Phase 1 Combined CG Calculator" (if the boss pushes)

## Open questions the user has raised

- Whether to reframe the FYP scope given the CAD layer is thin
- Whether to write a supervisor 1-pager / README update reflecting the agentic pivot
