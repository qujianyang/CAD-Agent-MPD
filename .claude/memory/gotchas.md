# Gotchas

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

LLM was truncating `to_s=0.011` to `to_s=0`, making physics blow up (division by zero in fn). Fixed with three-layer defense (see `conventions.md`). If you ever change a tool signature, double-check the OMIT instruction is still in the docstring.

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
