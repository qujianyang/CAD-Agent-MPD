# Tie-Down Provision Calculator — Replicator + Active Fastener Sizing (with AI)

- **Date:** 2026-05-29
- **Status:** Approved design (pending spec review by user)
- **Scope:** Domain module #2 in CAD-Agent-MPD (after `shock_mount`; `mobility` is module #3, deferred)
- **Source workbook:** `MCDLL Tie-Down Provision_20-8-2023.xlsx`

---

## 1. Goal & context

Replicate the *MCDLL Tie-Down Provision* Excel workbook as a validated Python engine — to the **same standard as the shock-mount tool** (reproduces the Excel to 4 decimal places) — and add a deterministic-tool LLM agent on top. This **extends the existing CAD-Agent-MPD app** as a second mechanical-engineering domain, reusing the embedder, agent, RAG, and UI.

Two-pillar framing (mirrors the project):
1. **Validated physics** — per-item, per-axis tie-down safety factors reproduced to 4 d.p.
2. **AI / RAG** — a **tab-routed specialist** agent with deterministic Python tools + hierarchical RAG over `knowledge/tiedown/`.

The CAD layer stays intentionally thin: tie-down is a bill-of-materials + fastener map, so it needs **no** SolidWorks dependency (CAD-sourced per-item weights deferred).

---

## 2. Decisions locked (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Build approach | **B — Replicator + active fastener sizing** | Reproduces the Excel *and* gives the agent real decision-making (the "select" analog of softest-valid-K). |
| Order | **Tie-down first**, mobility later | Tie-down maps most cleanly onto the shock pattern; de-risks the multi-domain refactor. |
| Integration | **Extend CAD-Agent-MPD** | Matches the "multiple mech-eng use cases" direction; reuses infra. |
| Inputs | **Structured input + Excel import** | Faithful to the sheet; no dependency on the thin/Education-blocked CAD layer. |
| Agent topology | **Tab-routed specialists** via `build_agent(domain)` | NVIDIA 70B does 1 tool-call/turn; focused per-domain tool sets beat a fat 15-tool agent. Deterministic tab routing = zero misclassification. |
| Router | **No LLM/embedding router** | User tried an embedding router before; it confused similar wordings → wrong tool. Recorded as a §-limitations finding, not a TODO. |
| Pass criterion | **SF ≥ 1.0** (Excel ultimate basis) | `size_fasteners` `target_SF` OMIT-defaults to 1.0. |
| Standard basis | Document G-values as **"per project Matrix 2 MCD(S) tie-down spec"** | External standard (MIL-STD-209 / Def Stan / DSTA?) marked **CONFIRM-WITH-SUPERVISOR**; never invented. |

---

## 3. Verified physics model (PROVEN: 177/177 SF to 4 d.p. across all 59 items)

A reverse-engineering check recomputed every item from `(weight, mount-face, fastener σ×area, qty)` and diffed against the workbook's own SF columns: **177/177 safety factors match, force-type mapping 100% correct, zero multi-face rows.**

### 3.1 Design forces (per item, per axis)
```
design_force_axis (N) = weight_kg × G_axis × g
  g = 9.81 ;  G_long = 4 ,  G_vert = 2 ,  G_lat = 1.5
```

### 3.2 Fastener strength — universal σ × area model
```
tensile_force_N = σt_MPa × area_mm²
shear_force_N   = σs_MPa × area_mm²
```
- **Bolts** (class 8.8 etc.): `σs = σt / 2`, `area` = minor-diameter area (M6 = 17.894 mm² …).
- **Spring latch / locking pin:** also `σs = σt / 2`, real area (spring latch = 113.097 mm², σt = 165).
- **Straps / ratchets / camlocks:** `area = 1`, `σt = σs = rated load (N)` (camlock 1" = 2500, ratchet 1" = 5000, camlock 1.5" = 18000 …).

The σs-halving is **not** a global rule — it is encoded per fastener type as stored in the workbook's *Fastener Data* sheet. Transcribe verbatim (same philosophy as the shock engine).

### 3.3 Mount face → force-type mapping (the core domain logic)
The face an item is fastened to determines, per load axis, whether the bolt sees **tension** or **shear**. The face is encoded in the workbook by which "Fastener Installation Qty" column is populated.

| Mount face | Normal | Long (X) | Vert (Z) | Lat (Y) |
|---|---|---|---|---|
| `WALL_X` — front/rear wall | X | **Tensile** | Shear | Shear |
| `FLOOR_Z` — floor/ceiling/top frame/base | Z | Shear | **Tensile** | Shear |
| `WALL_Y` — left/right side wall | Y | Shear | Shear | **Tensile** |

### 3.4 Safety factor (per axis)
```
exp_force_axis (N) = design_force_axis / qty           # equal load-sharing across all installed fasteners
SF_axis            = yield_force(type_axis) / exp_force_axis
  where yield_force = tensile_force_N if type==Tensile else shear_force_N
item passes  ⇔  min(SF_long, SF_vert, SF_lat) ≥ 1.0
```

### 3.5 Known source quirks (replicate, do not "fix")
- **Item 49** (*Mast Guying Kit*): weight cell = 59 kg but the design-force cells use **60 kg** (hardcoded override). On import, **trust the design-force cells**; for manual input, compute `W × G × g` normally. Document like the shock `/2` rule.
- The engine assumes **equal load sharing** across `qty` fasteners and **no CG-induced prying** — a faithful simplification of the source. Listed as a model limitation (good §-limitations content), not corrected.

---

## 4. Module layout (mirrors `shock_mount`)

| New / changed file | Analog of | Responsibility |
|---|---|---|
| `tiedown_engine.py` | `physics_engine.py` | dataclasses + `run_tiedown_analysis()` + `format_report()`; matches `.xlsx` to 4 d.p. |
| `fastener_catalog.py` | `catalog.py` | fasteners transcribed from *Fastener Data* + `size_fasteners()` (active sizing) |
| `tiedown_import.py` | (new) | parse the workbook into `Item` objects; used mainly as the validation fixture |
| `knowledge/tiedown/*.md` | `knowledge/shock_mount/` | 4 RAG docs, `parent_topic="tiedown"` |
| `agent.py` (refactor) | — | add `build_agent(domain)` factory + `DOMAINS` registry + tie-down tools |
| `app.py` (new tab) | — | "Tie-Down" tab: structured input + Excel import + results table + domain-scoped chat |
| `setup_knowledge.py` | (re-run) | embed the new `knowledge/tiedown/` chunks |
| `tests/` | — | validation harness (177/177) + smoke test + shock no-regression |

---

## 5. Data model (dataclasses, `tiedown_engine.py`)

```
DesignLoads(g=9.81, long_G=4.0, vert_G=2.0, lat_G=1.5)

FastenerSpec(name, kind, sigma_t_MPa, sigma_s_MPa, area_mm2)
  .tensile_force_N -> sigma_t_MPa * area_mm2
  .shear_force_N   -> sigma_s_MPa * area_mm2
  kind in {BOLT, SPRING_LATCH, LOCKING_PIN, STRAP, RATCHET, CAMLOCK, DRING}

MountFace(Enum): WALL_X, FLOOR_Z, WALL_Y
  .force_type(axis) -> "Tensile" | "Shear"   # per the §3.3 table

Item(name, weight_kg, mount_face, fastener: FastenerSpec, qty, design_override_kg=None)

AxisResult(axis, design_force_N, force_type, exp_force_N, yield_force_N, SF)
  .passed -> SF >= target_SF

ItemResult(item, axes: list[AxisResult])
  .min_SF, .limiting_axis, .passed

TiedownReport(items: list[ItemResult], loads: DesignLoads, target_SF, warnings)
  .all_passed, .critical_items(target_SF)
```

`format_report()` and a `_math_proof()`-style breakdown mirror the shock engine's formatting (ASCII, no non-ASCII symbols in source per conventions: use `[OK]`/`[FAIL]`).

---

## 6. Fastener catalog (`fastener_catalog.py`)

Transcribed verbatim from the workbook's *Fastener Data* sheet:
- **Property class → allowable yield stress (MPa):** A2-70=450, 4.6=240, 4.8=340, 5.8=420, 8.8=640, 9.8=720, 10.9=940, 12.9=1100 (σs = σt/2).
- **Bolt size → minor-diameter area (mm²):** M1.6 … M36, plus 1/4-20=21.712, etc.
- **Non-bolts (area=1, σt=σs=rated load N):** camlock 1"=2500, camlock 1.5"=18000, ratchet 1"=5000, ratchet 1.5"=30000, strap(net)=3500, D-ring=8896; **spring latch** = area 113.097, σt=165/σs=82.5; locking pin = area 28.274, σt=250/σs=125.

A bolt candidate = (class × size); a non-bolt candidate = a flat entry. Frozen dataclass `FastenerCatalogEntry` with `.to_fastener_spec()` (mirrors `CatalogEntry.to_isolator_spec()`).

---

## 7. Active fastener sizing (the "B" value-add)

Because `SF_axis = qty × yield(type) / design_axis`, sizing is **closed-form** (cleaner than the shock binary-search):
```
min_qty = ceil( max over axes of [ target_SF * design_force_axis / yield_force(type_axis) ] )
```

Tools wrapping it (deterministic; LLM never computes numbers):

| Tool | Analog | Purpose |
|---|---|---|
| `run_tiedown_check(...)` | `run_shock_analysis` | SF for one item or a whole BOM |
| `size_fasteners(weight_kg, mount_face, target_SF)` | `select_isolator` | smallest valid fastener + qty for the target SF |
| `find_min_fasteners(weight_kg, mount_face, fastener)` | `find_capacity_limit` | min qty for a chosen part |
| `flag_critical_items(target_SF)` | `filter_by_deflection` | items below target (surfaces water jerry cans @ SF 1.06) |
| `lookup_knowledge(query)` | (shared, scoped) | RAG over `knowledge/tiedown/` |

All tools follow the **OMIT rule** ("OMIT this parameter unless the user explicitly specifies it") and **NOTE injection** on substituted defaults (e.g. `target_SF` defaulted to 1.0).

---

## 8. Agent layer — tab-routed specialists

- Refactor `agent.py` to a **`build_agent(domain)`** factory reading a `DOMAINS` registry: `{ "shock_mount": (system_prompt, tools), "tiedown": (system_prompt, tools) }` → `create_agent(model, tools, system_prompt=...)`.
- **`build_agent("shock_mount")` must reproduce today's agent verbatim** (same prompt, same 7 tools). **Acceptance gate:** re-run the Tier 1-6 benchmark and confirm **no regression** (≥ 14/16 evaluable).
- Tie-down specialist = ~5 focused tools (§7). Each agent stays small → respects the 1-tool-per-turn 70B (`parallel_tool_calls=False`).
- Streamlit tab selects the domain; per-domain `chat_history` and `agent` kept in session state so switching tabs does not reset the other chat.

---

## 9. Knowledge / RAG (`knowledge/tiedown/`, 4 chunks)

| File | Contents |
|---|---|
| `design_loads.md` | the 4 G / 2 G / 1.5 G basis; cited as "per Matrix 2 spec"; external standard marked CONFIRM-WITH-SUPERVISOR |
| `force_types.md` | the mount-face → tensile/shear mapping + physical reasoning |
| `fastener_data.md` | classes, areas, strap/latch ratings (the catalog, in prose) |
| `selection_rules.md` | SF ≥ 1.0 pass rule; σs = σt/2-for-bolts convention; smallest-valid-fastener rule |

Each `.md` = one chunk; `parent_topic="tiedown"`, `child_name`=file stem. Re-run `setup_knowledge.py`.

---

## 10. UI (Streamlit, new "Tie-Down" tab)

- **Inputs:** structured per-item entry (name, weight, mount-face dropdown, fastener class/size or strap type, qty) + an "Import workbook" uploader.
- **Outputs:** per-item, per-axis SF table (Workings-style); a critical-items panel (SF below target highlighted); a `size_fasteners` helper widget.
- **Chat:** domain-scoped agent (`build_agent("tiedown")`) with streaming tool-call visibility, reusing the existing `st.status` + `_render_trace` pattern.

---

## 11. Validation strategy (§4 report material)

1. **Excel-match harness** — load the real `.xlsx`, recompute every item, diff vs the sheet's SF columns: target **177/177 to 4 d.p.** (already proven during design).
2. **Smoke test** pinned to the Generator: **SF = 4.9 / 19.599 / 13.066** (long/vert/lat) — the anchor (cf. shock GT = 6.296).
3. **Shock no-regression** — re-run Tier 1-6; must stay ≥ 14/16.
4. **Anti-hallucination** — confirm SF numbers in chat come only from tools (no LLM-invented values); NOTE injection fires on defaulted `target_SF`.

---

## 12. Non-goals (YAGNI — explicitly out of scope)

- Mobility / CG / turning-stability engine (module #3, same skeleton, later).
- LLM or embedding router (tab routing only).
- Excel **export** / round-trip import of arbitrary tie-down workbooks (importer targets *this* workbook's format as the validation fixture).
- CAD-sourced per-item weights.
- CG-induced prying / unequal load-sharing refinements.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Refactor breaks the working shock agent (14/16) | factory reproduces it verbatim; Tier 1-6 re-run is the acceptance gate |
| Excel importer fragile (multi-row headers, sparse "Allan" col, straps) | fixed column indices already proven (177/177); validation harness catches drift; structured form is the primary input |
| LLM invents SF numbers or a standard citation | all numbers from deterministic tools; OMIT rule + NOTE injection; standard basis documented, not invented |
| Source quirks (item 49 60-vs-59 kg; bolt-vs-strap shear) | strengths transcribed verbatim; trust design-force cell on import; documented |
| Multi-domain prompt/tool bloat | per-domain focused tool sets; small agents |

---

## 14. Open items

- **CONFIRM-WITH-SUPERVISOR:** the external standard behind 4 G / 2 G / 1.5 G (MIL-STD-209 / Def Stan / DSTA Matrix 2). Until confirmed, `design_loads.md` cites "per project Matrix 2 MCD(S) tie-down spec."

---

## 15. Acceptance criteria (Definition of Done)

1. `tiedown_engine.py` reproduces all 59 items' SF to 4 d.p. (harness 177/177).
2. `fastener_catalog.py` transcribed from *Fastener Data*; `size_fasteners` closed-form returns smallest valid part+qty.
3. Tie-down agent tools implemented with OMIT rule + NOTE injection.
4. `build_agent(domain)` factory; shock agent unchanged; Tier 1-6 ≥ 14/16 (no regression).
5. `knowledge/tiedown/` (4 docs) embedded; `lookup_knowledge` scoped to the topic.
6. New "Tie-Down" Streamlit tab: structured input + import + results + domain chat.
7. Smoke test pins Generator SF (4.9 / 19.599 / 13.066).
8. No non-ASCII symbols in source; project venv (`mpd\Scripts\python.exe`); `.env` for keys only.
