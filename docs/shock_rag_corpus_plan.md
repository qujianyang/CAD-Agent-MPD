# Shock-Only RAG Corpus — Build Plan & Source Intake

Kept **outside** `knowledge/` so `setup_knowledge.py` never embeds it. This is
the tracker for the shock-only RAG rebuild and the checklist of source files
still needed.

Decisions on record (2026-07-13):
- **Scope:** LLM/RAG evaluation covers `shock_mount` **only**. The final
  manifest and 170-case benchmark must state this. (tiedown / mobility folders
  stay on disk but are out of scope for the frozen shock eval.)
- **Grounding rule:** Python owns catalogue values, calculations, and
  PASS/FAIL/ASK. RAG supplies references, assumptions, procedures, and
  source-grounded explanations. RAG is **not** a second calculator.
- **Populate now:** scaffold + grounded fill. **Layout:** rebuild in place in
  `knowledge/shock_mount/`, keep the 5 original files until migration is
  verified, then delete them.

## Chunk ID = filename

`setup_knowledge.py` sets each chunk `id = "shock_mount/<filename-stem>"`.
**Filenames are the stable chunk IDs** — freeze the names before hashing the
index. Do not rename after freeze.

## Received 2026-07-13 (batch 1: VMC datasheets + Tech Notes)

Files processed: CB1400 Rev.5, CB1500 Rev.6, CB1700.pdf, Wire Rope Tech Notes.
(PDFs are rasterized; extracted via pypdf image dump + vision OCR into scratchpad.)

**Filled / confirmed:**
- Manufacturer corrected to **The VMC Group** (Helical Series; Aeroflex heritage,
  acquired by VMC in 2005) — `catalog.py` says "Helical / Aeroflex".
- **cb1400_catalog** — CB1400 Rev.5; all K / shear / travel / vib-K values match
  `catalog.py` exactly. Datasheet also has a "45 DEG C/R" mode (unused) and
  publishes Vib-K for -10/-12/-25 (which `catalog.py` left `None`).
- **cb1500_catalog** — CB1500 Rev.6; the 6 loaded variants match exactly.
  Datasheet has 11 variants (-10..-70); 5 are not in `catalog.py`.
- **impulse_velocity / pulse_sawtooth / pulse_half_sine** — the velocity-step
  energy method and pulse coefficients (half-sine 2/π, triangular/sawtooth 1/2,
  square 1) are now sourced to the **VMC Tech Notes**. So is fn/GT/ΔD.
- **model_assumptions / model_limitations / installation_considerations** —
  two-spring-rate method, third-order softening curve, 15–20% damping,
  tension-direction caution, 3:1–4:1 frequency ratio, CG-rocking.

**Still outstanding after batch 1:**
- **20 G / 11 ms / 10 G values** — NOT in these files (Tech Notes example is
  30 G / 11 ms half-sine). Need MIL-STD-810 shock pages + project/fragility spec.
- **Max Static F** — NOT on the VMC datasheets. → RESOLVED in batch 2 (Socitec
  `Helical_English.pdf`).
- **CB1700** — supplied `CB1700.pdf` is empty. → RESOLVED in batch 2 (Aeroflex
  `helical.pdf` + Socitec).
- **CB61400** — datasheet not in batch 1. → RESOLVED in batch 2 (Aeroflex
  `helical.pdf`).

## Received 2026-07-13 (batch 2: Aeroflex + Socitec catalogs)

Files processed: `helical.pdf` (Aeroflex "HELICAL" master catalog, 7pp, text) and
`Helical_English.pdf` (Socitec "'helical' performances", 44pp; table pages have a
text layer).

**Provenance now fully resolved — the catalog is a 3-source composite:**
- **K, Vibration K, rated travel** ← Aeroflex `helical.pdf` (master; covers the
  whole family incl. CB61400/CB1400/CB1500/CB1700). Confirmed by the VMC Rev.5/6
  datasheets (batch 1). VMC = current maker (acquired Aeroflex 2005).
- **Max Static F (comp + shear)** ← Socitec `Helical_English.pdf`, pp.30/32/36.
  Every value matches `catalog.py` exactly. Socitec is a distinct EU vendor of
  the equivalent line (dated 2005).

**Newly confirmed/closed:**
- **cb1700_catalog** — K/travel confirmed via `helical.pdf` p.16; static F via
  Socitec p.36. The empty `CB1700.pdf` no longer blocks anything.
- **cb61400_optional_scope** — K/travel confirmed via `helical.pdf` p.15.
- **static_load_gate** — Max Static F confirmed to Socitec pp.30/32/36; also
  explains why CB1400-10/-25 and all CB61400 are unrated (absent from Socitec).

**Still outstanding (unchanged):** the 20 G / 11 ms / 10 G *values* still need
MIL-STD-810 shock pages + project/fragility spec (see `project_shock_requirements`).

## Migration completed 2026-07-14 (corpus freeze step 1)

- **Verified the 20 G / 11 ms basis directly from `MIL-STD-810H.pdf`** (scanned
  table page extracted and read): Table 516.8-IV, method page 516.8-23 —
  Ground Materiel 40 G / 11 ms, reduced to 20 G by Note 3 (trucks/semi-trailers);
  Note 1 half-sine equivalence `Am(hs) = (pi/4)*Am(st)` for shock-mounted or
  > 136 kg items; para 4.6.2 classical-pulse caveats. Filled into
  `project_shock_requirements.md`, `pulse_sawtooth.md`, `pulse_half_sine.md`,
  `transmitted_g_limit.md`. Only the customer-side 10 G document remains open.
- **Migrated remaining legacy content**: series quick-reference + typical mount
  configurations + engineer-override reasons → `selection_workflow.md`;
  road-vibration check (vib K, PSD method, SPF_Vibration validation) → new
  chunk `road_vibration_check.md`.
- **Deleted the 5 legacy files**: `catalog_overview.md`, `formulas.md`,
  `load_cases.md`, `mil_std_basis.md`, `selection_rules.md`.
- **Frozen corpus = 34 chunks** (28 rebuilt/authored + 6 user `mil_std_516_8_*`).
  Chunk IDs = filenames; do not rename after the index hash is recorded.
- Note: `evaluation/retrieval_qrels_shock_v1.jsonl` and any retrieval results
  computed against the pre-migration corpus reference stale chunk IDs — re-check
  before reuse.

## The 27 chunks and their status

Grounding legend: **G** = filled from validated in-repo artifacts ·
**H** = hybrid (values grounded, provenance slots open) ·
**A** = awaiting source (structure + slots only).

| # | File | G/H/A | Still needs |
|---|------|-------|-------------|
| 1 | standard_scope.md | A | standard identity + scope pages |
| 2 | project_shock_requirements.md | A | **origin of 20 G / 11 ms / 10 G** |
| 3 | pulse_sawtooth.md | G/H | method sourced (VMC); why-sawtooth-default still needs MIL-STD/project spec |
| 4 | pulse_half_sine.md | G/H | Idea-1 sourced (VMC); MIL-STD equal-velocity substitution clause still open |
| 5 | transmitted_g_limit.md | H | equipment/customer fragility doc for 10 G |
| 6 | load_distribution.md | G | — |
| 7 | four_load_cases.md | G | — |
| 8 | impulse_velocity.md | G | method now sourced to VMC Tech Notes |
| 9 | natural_frequency.md | G | — |
| 10 | transmitted_acceleration.md | G | — |
| 11 | dynamic_deflection.md | G | — |
| 12 | static_load_gate.md | G | Max Static F CONFIRMED vs Socitec pp.30/32/36 |
| 13 | travel_limit_gate.md | G | — |
| 14 | governing_check.md | G | — |
| 15 | selection_workflow.md | G | — |
| 16 | verification_workflow.md | G | — |
| 17 | max_clearance_objective.md | G | — |
| 18 | best_isolation_objective.md | G | — |
| 19 | missing_input_policy.md | G | — |
| 20 | cb1400_catalog.md | G | CONFIRMED vs VMC CB1400 Rev.5 |
| 21 | cb1500_catalog.md | G | CONFIRMED vs VMC CB1500 Rev.6 |
| 22 | cb1700_catalog.md | G | CONFIRMED vs Aeroflex helical.pdf p.16 + Socitec p.36 |
| 23 | cb61400_optional_scope.md | G | CONFIRMED vs Aeroflex helical.pdf p.15 |
| 24 | installation_considerations.md | H | vendor mounting / ST Eng practice |
| 25 | validation_excel_baseline.md | G/H | workbook author/date/tolerance |
| 26 | model_assumptions.md | G | — |
| 27 | model_limitations.md | G | — |

## Source intake — what to send, and which slots it fills

1. **MIL-STD-810 (or governing standard) shock-method pages / approved extracts**
   → fills: standard_scope (1), project_shock_requirements (2),
   pulse_sawtooth (3), pulse_half_sine (4).
   Extract exactly: method/procedure number, the peak+duration default table and
   its notes, the pulse-substitution clause. Do not infer beyond the text.

2. **Project / customer shock specification**
   → fills: project_shock_requirements (2), standard_scope (1) tailoring.
   Extract: required Ao, to, pulse shape, directions, acceptance criteria, and
   whether these are standard defaults or internal requirements.

3. **Equipment / customer fragility (transmitted-G) document**
   → fills: transmitted_g_limit (5).
   Extract: the 10 G origin, which equipment sets it, strict vs non-strict.

4. **Manufacturer datasheets: CB1400, CB1500, CB1700 (and CB61400 if kept)**
   → fills: cb1400/1500/1700_catalog (20–22), cb61400_optional_scope (23),
   static_load_gate (12) page refs.
   Extract per part: exact part number, K_comp, K_shear, rated comp travel,
   rated shear travel, Max Static F, dimensions, recommended orientation, and
   the source document name / revision / page / manufacturer. Cross-check the
   numeric values against `catalog.py`; flag any mismatch rather than
   overwriting silently.

5. **Validated Excel workbook** (`Shock Isolator_850kg_4 Bayed 35U.xls`)
   → fills: validation_excel_baseline (25).
   Extract: author/owning group, date/revision, documented Excel↔Python
   tolerance. (Engineering numbers already validated in-repo.)

6. **ST Engineering workflow / design rule / installation standard** (if permitted)
   → fills: selection_workflow (15), installation_considerations (24).

## After sources arrive

1. Fill every `[SOURCE NEEDED]` / `[CONFIRM]` slot from the supplied files only.
2. Reconcile any datasheet↔`catalog.py` value mismatches (report, don't
   overwrite silently).
3. Remove the 5 legacy files once their content is fully migrated:
   `catalog_overview.md`, `formulas.md`, `load_cases.md`, `mil_std_basis.md`,
   `selection_rules.md`.
4. Confirm the manifest declares `shock_mount` only for the LLM eval.
5. `.\mpd\Scripts\python.exe setup_knowledge.py` to build the index, then record
   the chunk IDs + index hash in the freeze docs.

## Known issue fixed during scaffold

Old `selection_rules.md` said the default is "softest valid part". The shipping
default objective in `catalog.py` is `max_clearance` = **stiffest** first. The
new `max_clearance_objective.md` / `best_isolation_objective.md` state the code's
actual behaviour. Do not reintroduce the "softest is default" wording.
