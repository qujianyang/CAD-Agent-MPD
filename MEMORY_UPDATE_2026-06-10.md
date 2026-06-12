# Memory update — 2026-06-10 session (mobility scenario workspace)

`.claude/memory/` was write-protected in this session. Merge the two sections
below into the named files, then delete this file.

---

## ADD to top of `.claude/memory/current-status.md` (and bump its date)

## Mobility Scenario Workspace (NEW, 2026-06-10)

Replaced the disconnected Full Analysis / Custom CG / Cornering Calculator sections in the Mobility tab with one traceable workflow. All 4 phases complete, pending user's local Streamlit click-through.

- **`mobility_scenarios.py`** (new, pure, no Streamlit/IO): `vehicle_from_wheel_loads` (SAR App. B moment balance; Ycg right-positive matches engine), `vehicle_from_certified_cg` (mandatory source label), `MassChange` + `apply_mass_changes` (add/remove/relocate via moment summation; relocate = same mass, moment shift), `baseline_delta`, `check_cg_plausibility` (soft warnings), `sf_verdict` 3-tier (UNSTABLE / BELOW MARGIN / MEETS MARGIN) with OEM margins 2.0 long / 2.2 lat / 2.2 corner, `margin_for_direction`.
- **`tests/test_mobility_scenarios.py`**: 60 tests, all passing. Anchors: wheel loads 4000/3975/4750/5125 -> GW 17,850 / Xcg 2655.462 / Ycg 20.471; Ycg sign-convention test; no-change identity; invalid-input rejections; engine integration.
- **`app.py` mobility tab** now: (1) scenario builder with 4 modes -- Workbook baseline (default) / Wheel-load measurement / Design-modification study (st.data_editor dynamic table) / Advanced certified CG (collapsed) -- (2) derived vehicle summary + provenance + datum caption + baseline-vs-modified deltas, (3) unified assumptions (grades 60/50 + 30/25, 15 km/h, 11 m, 60 km/h wind, editable OEM margins), (4) unified results (axle/GVW/steerability margin table, slope SF table with verdicts, cornering, console expanders), (5) SAR generation (unchanged logic, reads session-state path/variant with fallbacks), (6) assistant.
- State keys: `mb_vehicle` / `mb_prov` / `mb_approach` / `mb_report` / `mb_base`. Any failed build/read clears all (no stale results). New vehicle invalidates old report.
- Engine (`mobility_engine.py`) untouched -- all validated equations intact.
- Full suite at last run: 132 passed in sandbox (LangChain-dependent test files not runnable there; run `.\mpd\Scripts\python.exe -m pytest -q` locally for full set).
- **Not yet committed**; tab not yet click-tested in Streamlit.

---

## ADD to `.claude/memory/gotchas.md`

## Cowork sandbox mount -- edited files truncate, stale .pyc (2026-06-10)

When working through Claude's Cowork sandbox (Linux mount of this repo):
- **Files EDITED via file tools sync unreliably to the sandbox mount** -- they can freeze truncated mid-file. The Windows-side file is always canonical and correct; only the sandbox's read copy corrupts. NEW files sync fine. Workaround: mirror changed code into a new filename to compile/test it in the sandbox, then delete the mirror.
- **Stale `__pycache__` .pyc**: pytest can execute old bytecode while showing new source in tracebacks (AttributeError on a line that looks correct). Sandbox can't delete the mount's `__pycache__` ("Operation not permitted"). Fix: `PYTHONPYCACHEPREFIX=/tmp/pyc python -m pytest ...` (use a fresh prefix dir if it was populated before the edit).
- None of this affects running locally on Windows.

## Streamlit st.data_editor (mobility mod table)

`mb_mod_table` uses list-of-dicts + `num_rows="dynamic"`. New rows arrive with `None` values -- the parse loop must skip rows with empty Action/Mass and pass `None` coords through (module validates per-action). Don't convert to pandas; keeps app dependency-light.
