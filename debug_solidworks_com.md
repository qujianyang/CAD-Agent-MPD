# SolidWorks COM — ActiveDoc Debug Notes

## Problem

App connected to SolidWorks successfully but returned "No active SolidWorks document" even with a file open.

## Root Cause

Two distinct COM dispatch modes exist in `win32com`, and they expose **different subsets** of the SolidWorks API:

| Dispatch mode | How to get it | What it exposes | What it hides |
|---|---|---|---|
| **Early-bound (typelib)** | `gencache.EnsureDispatch("SldWorks.Application")` | Typed methods: `Extension.CreateMassProperty()`, `OpenDoc6()`, etc. | `ActiveDoc` — throws "Member not found" |
| **Late-bound (dynamic)** | `GetObject(Class="SldWorks.Application")` or `dynamic.Dispatch(sw)` | `ActiveDoc`, `GetFirstDocument()` | Some typed methods may be inaccessible |

The SolidWorks typelib (the COM type library that EnsureDispatch uses to generate Python wrappers) exposes `IActiveDoc2` as a **write-only property** (a setter, not a getter). So trying to read it via the typelib wrapper raises:

```
Unable to read write-only property
```

And trying `ActiveDoc` directly raises:

```
Member not found
```

Both are the same underlying issue: the typelib drops the getter entirely.

## Diagnostic output that revealed this

```
[DIAG] SW sees 3 open document(s)
[DIAG] sw.ActiveDoc -> EXCEPTION: Member not found
[DIAG] IActiveDoc2 -> EXCEPTION: Unable to read write-only property
[DIAG] sw_late.ActiveDoc -> <win32com object at 0x...>  <- works
```

The late-bound reference exposed `ActiveDoc` correctly because it bypasses the typelib and uses dynamic IDispatch — which is what SolidWorks's actual COM server exposes.

## Fix (test_assembly.py)

Maintain **two** COM references to the same SolidWorks process:

```python
import win32com.client
import win32com.client.dynamic

# sw_late: late-bound via ROT (Running Object Table) — ActiveDoc works here
sw_late = None
try:
    sw_late = win32com.client.GetObject(Class="SldWorks.Application")
except Exception:
    pass

# sw: typelib-wrapped (early-bound) — typed methods like CreateMassProperty() work here
try:
    sw = win32com.client.gencache.EnsureDispatch("SldWorks.Application")
except Exception:
    sw = sw_late or win32com.client.Dispatch("SldWorks.Application")

# If GetObject failed (SW not running yet), wrap the typelib object in dynamic dispatch
if sw_late is None:
    sw_late = win32com.client.dynamic.Dispatch(sw)
```

Then use the right reference for each operation:

```python
# ActiveDoc — MUST use late-bound
model_raw = sw_late.ActiveDoc

# Mass properties — MUST use typelib-wrapped sw
mp = model.Extension.CreateMassProperty2()
```

## Why both are needed

- `sw_late.ActiveDoc` — only works via late-bound (dynamic) dispatch
- `sw.Extension.CreateMassProperty2()` / `sw.OpenDoc6()` — only works via typelib (early-bound) because these are typed COM methods that `dynamic.Dispatch` can call but may return untyped `VARIANT` results that are harder to work with

## Fallback chain for active document

```python
# 1. Try ActiveDoc (most reliable when a doc is in the foreground)
try:
    model_raw = sw_late.ActiveDoc
except Exception:
    model_raw = None

# 2. Fallback: GetFirstDocument (works if only one doc is open)
if model_raw is None:
    try:
        model_raw = sw_late.GetFirstDocument()
    except Exception:
        pass

# 3. Error out — no silent fallback
if model_raw is None:
    raise RuntimeError(
        "No --file specified and no active SolidWorks document. "
        "Either open a model in SolidWorks first, or pass --file PATH."
    )
```

## Key lesson

`EnsureDispatch` is **not** a strict superset of `GetObject`/`dynamic.Dispatch`. For SolidWorks specifically:
- The typelib gives you typed, validated method calls
- Dynamic dispatch gives you property access that the typelib author chose to omit

You need both. This is specific to the SolidWorks COM server design — other COM servers may differ.
