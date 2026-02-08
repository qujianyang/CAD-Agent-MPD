import win32com.client
import sys
import pythoncom

# Initialize COM
pythoncom.CoInitialize()

# Sheet metal feature type names
SHEET_METAL_FEATURES = {
    "SheetMetal", "SMBaseFlange", "EdgeFlange", "Hem", "Jog", "LoftedBend",
    "FlatPattern", "Fold", "UnFold", "Bending", "OneBend", "SketchBend",
    "SM3dBend", "CornerTrim", "BreakCorner", "CrossBreak", "ProcessBends",
    "FlattenBends", "FormToolInstance"
}

def debug_step(msg):
    print(f"[DEBUG] {msg}...", end=" ", flush=True)

def safe_call(obj, attr_name, *args):
    if obj is None:
        return None
    try:
        attr = getattr(obj, attr_name)
    except Exception:
        return None
    try:
        return attr(*args) if callable(attr) else attr
    except Exception:
        return None

try:
    # Use GetObject to attach to a running instance, fall back to Dispatch
    debug_step("Connecting to SOLIDWORKS")
    try:
        sw = win32com.client.GetObject(Class="SldWorks.Application")
    except Exception:
        # Try EnsureDispatch to force early binding for CastTo to work reliably
        try:
            sw = win32com.client.gencache.EnsureDispatch("SldWorks.Application")
        except:
            sw = win32com.client.Dispatch("SldWorks.Application")
    
    sw.Visible = True
    sw.UserControl = True
    print("OK")

    debug_step("Getting Active Document")
    def com_get(obj, name):
        try:
            v = getattr(obj, name)
            return v() if callable(v) else v
        except Exception:
            return None

    model_raw = com_get(sw, "IActiveDoc2") or com_get(sw, "ActiveDoc")
    
    if model_raw is None:
        PART_PATH = r"c:\Users\user\Downloads\17715A73_Galvanized Steel Corner Bracket.SLDPRT"
        debug_step(f"No active doc, opening '{PART_PATH}'")
        try:
            errs = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warns = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            model_raw = sw.OpenDoc6(PART_PATH, 1, 1, "", errs, warns)
            print("OK")
        except Exception as e:
            print(f"FAILED ({e})")

    if model_raw is None:
        raise RuntimeError("No active document found.")
    print("OK")

    # Cast to specific interfaces for reliable property/method access
    debug_step("Casting to ModelDoc2/PartDoc")
    try:
        model = win32com.client.CastTo(model_raw, "IModelDoc2")
    except:
        model = model_raw
    
    try:
        part = win32com.client.CastTo(model_raw, "IPartDoc")
    except:
        part = model_raw
    print("OK")

    debug_step("Checking document type")
    doc_type = safe_call(model, "GetType")
    print(f"OK (Type: {doc_type})")

    debug_step("Getting Active Configuration")
    cfg_name = ""
    try:
        cfg_mgr = safe_call(model, "ConfigurationManager")
        cfg = safe_call(cfg_mgr, "ActiveConfiguration")
        cfg_name = safe_call(cfg, "Name") or ""
    except Exception:
        pass
    if not cfg_name:
        try:
            cfg = safe_call(model, "GetActiveConfiguration")
            cfg_name = safe_call(cfg, "Name") or ""
        except:
            cfg_name = ""
    print(f"OK ({cfg_name or '<active>'})")

    # --- Material ---
    debug_step("Reading Material")
    material = "N/A"
    try:
        res = None
        try:
            # Try with ByRef database name (common requirement for some bindings)
            db = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
            res = part.GetMaterialPropertyName2(cfg_name or "", db)
        except Exception:
            # Fallback to simple call
            res = part.GetMaterialPropertyName2(cfg_name or "", "")

        if isinstance(res, (tuple, list)):
            material = res[0]
        else:
            material = res or ""
        print(f"OK ({material})")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Part Type ---
    debug_step("Analyzing Features for Part Type")
    is_sheet = False
    try:
        feat = safe_call(model, "FirstFeature")
        while feat:
            t = safe_call(feat, "GetTypeName2")
            if t in SHEET_METAL_FEATURES:
                is_sheet = True
                break
            feat = safe_call(feat, "GetNextFeature")
        part_type = "Sheet Metal" if is_sheet else "Solid"
        print(f"OK ({part_type})")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Bounding Box ---
    debug_step("Calculating Bounding Box")
    try:
        box = part.GetPartBox(True)
        if box:
            x1, y1, z1, x2, y2, z2 = box
            dx, dy, dz = abs(x2 - x1), abs(y2 - y1), abs(z2 - z1)
            print(f"OK ({dx:.3f}x{dy:.3f}x{dz:.3f})")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Mass ---
    debug_step("Calculating Mass")
    try:
        mass_kg = None
        ext = safe_call(model, "Extension")
        if ext:
            mp = safe_call(ext, "CreateMassProperty2") or safe_call(ext, "CreateMassProperty")
            if mp:
                try:
                    mp.UseSystemUnits = True
                except: pass
                mass_val = safe_call(mp, "Mass")
                if mass_val is not None:
                    mass_kg = float(mass_val)

        if mass_kg is None:
            mass_props = safe_call(model, "GetMassProperties")
            if mass_props:
                mass_kg = float(mass_props[5])

        if mass_kg is not None:
            print(f"OK ({mass_kg:.4f} kg)")
        else:
            print("FAILED (API unavailable)")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Custom Properties ---
    debug_step("Reading Custom Properties")
    props = {}
    try:
        # Access Extension directly from casted model
        ext = model.Extension
        cpm = None
        if ext:
            cpm = ext.CustomPropertyManager(cfg_name or "")
            if cpm is None:
                cpm = ext.CustomPropertyManager("")

        if cpm:
            names = cpm.GetNames()
            if names:
                for n in names:
                    res = cpm.Get4(n, False, "", "")
                    if isinstance(res, (tuple, list)):
                        props[n] = res[2] if len(res) > 2 else res[1]
                    else:
                        props[n] = res
            print(f"OK ({len(props)} found)")
            print(f"Properties: {props}")
        else:
            print("FAILED (CustomPropertyManager unavailable)")
    except Exception as e:
        print(f"FAILED ({e})")

except Exception as e:
    print(f"\n[CRITICAL ERROR] {e}")