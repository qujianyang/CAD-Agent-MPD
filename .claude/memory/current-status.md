# Current Status

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
