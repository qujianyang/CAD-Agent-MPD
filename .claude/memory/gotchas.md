# Gotchas

## Repo layout after the 2026-06-08 declutter

- Source `.py` modules are still **flat at root** (imports unchanged). Only data/docs/tests/scripts moved.
- `data/` = committed source inputs (workbooks, `iso_select[1].pdf`). `artifacts/` = **gitignored**, regenerable embeddings + demo `.docx`.
- Embedding stores now live in `artifacts/` (`artifacts/knowledge_embeddings.json`, `artifacts/mil_std_embeddings.json`). These paths are **cwd-relative** → **always run from the repo root** or they won't resolve.
- `tests/` holds the pytest suite (`pytest.ini` sets `testpaths=tests`; `tests/conftest.py` puts root on `sys.path`). Run: `.\mpd\Scripts\python.exe -m pytest`.
- **`test_assembly.py` stays at root** — it's the SolidWorks COM runtime script (subprocess-launched by `cad_compliance_checker.py` + `app.py`), NOT a pytest test. `scripts/test_part.py` and `scripts/test_api.py` are also manual diagnostics, not pytest.
- `WB_DEFAULT` in `tiedown_import.py` / `mobility_import.py` now defaults to the committed `data/` copies (anchored via `__file__`, so cwd-independent), keeping the repo self-contained. Override with env vars `TIEDOWN_XLSX` / `MOBILITY_XLS` to point at a newer/local revision. Heads-up: the `data/` tie-down workbook is the **validated 14 kg snapshot** the engine + tests are pinned to; a newer Downloads revision had Air-Con at 20 kg / 7 bolts. If you adopt the newer numbers, refresh `data/` AND update `tests/test_tiedown_import.py` expectations.

## SolidWorks Education Edition blocks API methods

**Symptom:** `CreateMassProperty`, `GetCoordinateSystemTransformByName2`, and other `IModelDocExtension` methods return `"Member not found"` via late-binding dispatch — even with `gencache.EnsureDispatch`.

**Workaround in `test_assembly.py`:**
- **Path A** (commercial license): `IMassProperty.SetCoordinateSystem("Mounting_Base")`. **Keep this code.**
- **Path B** (Education Edition fallback): use bounding box to translate CG into base frame: `CG_z_base = CG_z_default - z_min_bbox`.

Both paths are wired; the script picks whichever returns valid numbers. The user's machine **has the commercial license**, so Path A should work there. Don't delete Path B — it's the only thing that works on Education Edition.

## NVIDIA hosted endpoint — single tool call per turn

**Symptom:** 400 error mentioning "single tool-calls at once".
**Fix:** `ChatNVIDIA(..., parallel_tool_calls=False)`.

## LangChain 1.x API churn

`create_tool_calling_agent` is **gone**. Use `create_agent` from `langchain.agents`. Returns a `CompiledStateGraph`; invoke with a messages dict.

## xlrd can't read .xls formulas

xlrd only sees computed values, not the formula text. To inspect formulas in the validated Excel:
```python
import win32com.client
xl = win32com.client.gencache.EnsureDispatch("Excel.Application")
wb = xl.Workbooks.Open(path)
formula = wb.Sheets("Sheet1").Range("E21").Formula
```

## The to_s=0 LLM hallucination

LLM was truncating the small decimal `to_s=0.011` to `to_s=0`, making physics blow up (division by zero in fn). **Primary fix (2026-06): the model-facing pulse-duration param is now `to_ms` in milliseconds (default `11.0`)** on all four shock tools (`select_isolator`, `run_shock_analysis`, `find_capacity_limit`, `filter_by_deflection`). Each tool converts `to_s = to_ms / 1000.0` internally; `ShockEnv.to_s` stays SI seconds. An integer-scale value is far less likely to be truncated, and this is model-agnostic. The runtime clamp + NOTE substitution is retained as a backstop (three-layer defense, see `conventions.md`). If you ever change a tool signature, double-check the OMIT instruction is still in the docstring.

## Stale Streamlit processes pile up

After multiple `streamlit run` invocations, old processes hang around on different ports. Kill all:
```powershell
Get-Process | Where-Object { $_.ProcessName -eq "streamlit" -or $_.Path -like "*streamlit*" } | Stop-Process -Force
```

## Streamlit nothing-happens-on-click

If a subprocess errors and you don't surface stderr, the UI just sits there with the spinner gone and no message. **Always** show returncode + stderr expander. `run_solidworks_extraction` returns a 4-tuple for this reason.

## Tool-arg invention (T6.3-style)

If the agent invents a parameter name (e.g. `dD_mm` instead of using a real arg), add a properly-named tool rather than catching the typo. `filter_by_deflection(max_dD_mm=...)` was added for this exact reason.

## Feature walk silently returns None

The original `safe_call` wrapper around COM attribute access was silently catching `AttributeError` and returning None. The feature tree walk in `test_assembly.py` would terminate after one feature. **Direct attribute access (`model.FirstFeature`, `feat.Name`, `feat.GetNextFeature()`) is the only reliable pattern.**

## NVIDIA API key hardcoding

Several files (`cad_compliance_checker.py`, `mil_std_rag.py`, `setup_rag.py`) previously had hardcoded API key fallbacks. They've been removed. **Do not put them back** — they leak into git history.
