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
        PART_PATH = r"C:\mpd\models\SOLIDWORKS DATABASE\Equipment Rack\40U Rack.SLDASM"
        doc_type = 2 if PART_PATH.lower().endswith(".sldasm") else 1
        debug_step(f"No active doc, opening '{PART_PATH}' as doc type {doc_type}")
        try:
            errs = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warns = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            model_raw = sw.OpenDoc6(PART_PATH, doc_type, 1, "", errs, warns)
            print("OK")
        except Exception as e:
            print(f"FAILED ({e})")

    if model_raw is None:
        raise RuntimeError("No active document found.")
    print("OK")

    # Cast to specific interfaces for reliable property/method access
    debug_step("Casting to ModelDoc2/AssemblyDoc")
    try:
        model = win32com.client.CastTo(model_raw, "IModelDoc2")
    except:
        model = model_raw

    debug_step("Checking document type")
    doc_type = safe_call(model, "GetType")
    is_assembly = (doc_type == 2)
    print(f"OK (Type: {'Assembly' if is_assembly else 'Part'} [{doc_type}])")

    try:
        assembly = win32com.client.CastTo(model_raw, "IAssemblyDoc") if is_assembly else None
        part = win32com.client.CastTo(model_raw, "IPartDoc") if not is_assembly else None
    except:
        assembly = model_raw if is_assembly else None
        part = model_raw if not is_assembly else None
    print("OK")

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
        if is_assembly:
            print("OK (SKIPPED for assembly)")
        else:
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

    # --- Bounding Box (Assembly Envelope OR Part Box) ---
    debug_step("Calculating Bounding Envelope")
    width_mm = depth_mm = height_mm = None
    try:
        box = None
        if is_assembly:
            # Union all top-level component bounding boxes for full envelope
            top_comps = safe_call(assembly, "GetComponents", True)  # True = top-level only
            if top_comps:
                xs_min, ys_min, zs_min = [], [], []
                xs_max, ys_max, zs_max = [], [], []
                for c in top_comps:
                    cbox = safe_call(c, "GetBox", False, False)
                    if cbox and len(cbox) >= 6:
                        xs_min.append(cbox[0]); ys_min.append(cbox[1]); zs_min.append(cbox[2])
                        xs_max.append(cbox[3]); ys_max.append(cbox[4]); zs_max.append(cbox[5])
                if xs_min:
                    box = [min(xs_min), min(ys_min), min(zs_min),
                           max(xs_max), max(ys_max), max(zs_max)]
        else:
            box = part.GetPartBox(True)

        if box and len(box) >= 6:
            x1, y1, z1, x2, y2, z2 = box[:6]
            width_mm = abs(x2 - x1) * 1000   # X
            depth_mm = abs(y2 - y1) * 1000   # Y
            height_mm = abs(z2 - z1) * 1000  # Z
            print(f"OK (W:{width_mm:.1f}mm x D:{depth_mm:.1f}mm x H:{height_mm:.1f}mm)")
        else:
            print("FAILED (no box data)")
    except Exception as e:
        print(f"FAILED ({e})")


    # --- Mass Properties (try Mounting_Base transform, fall back to origin) ---
    debug_step("Extracting Mass Properties")
    coord_ref = "DEFAULT_ORIGIN"
    mass_kg = volume_mm3 = surface_mm2 = cg_x = cg_y = cg_z = None
    try:
        # Step 1: Get raw mass properties (always in MODEL/WORLD frame)
        mass_props = safe_call(model, "GetMassProperties")
        if mass_props and len(mass_props) >= 6:
            cg_world_m = (float(mass_props[0]), float(mass_props[1]), float(mass_props[2]))
            volume_mm3 = float(mass_props[3]) * 1e9
            surface_mm2 = float(mass_props[4]) * 1e6
            mass_kg = float(mass_props[5])

            # Default: CG in world/model frame (mm)
            cg_x = cg_world_m[0] * 1000
            cg_y = cg_world_m[1] * 1000
            cg_z = cg_world_m[2] * 1000

            # Step 2: Try to transform CG into Mounting_Base coord system
            try:
                ext = model.Extension
                xform = ext.GetCoordinateSystemTransformByName("Mounting_Base")
                if xform is not None:
                    math_util = sw.GetMathUtility()
                    point_world = math_util.CreatePoint(list(cg_world_m))
                    inv = xform.Inverse
                    point_local = point_world.MultiplyTransform(inv)
                    arr = point_local.ArrayData
                    if arr and len(arr) >= 3:
                        cg_x = float(arr[0]) * 1000
                        cg_y = float(arr[1]) * 1000
                        cg_z = float(arr[2]) * 1000
                        coord_ref = "MOUNTING_BASE"
            except Exception as e:
                print(f"  [info] Mounting_Base transform unavailable ({str(e)[:80]}), using model origin")

        mp = True  # signal success
    except Exception as e:
        print(f"  [debug] mass prop extraction error: {e}")
        mp = None

    if mass_kg is not None:
        print(f"OK (coord_sys={coord_ref})")
        print(f"  -> Mass:         {mass_kg:.4f} kg ({mass_kg*1000:.2f} grams)")
        print(f"  -> Volume:       {volume_mm3:.2f} mm³")
        print(f"  -> Surface Area: {surface_mm2:.2f} mm²")
        print(f"  -> Center of Mass (CG): X={cg_x:.2f}mm, Y={cg_y:.2f}mm, Z={cg_z:.2f}mm")
        if coord_ref == "DEFAULT_ORIGIN":
            print("  ⚠ Note: CG is relative to model origin. Create 'Mounting_Base' coord system for true floor-relative CG.")
    else:
        print("FAILED (no mass data)")

    # --- Custom Properties (config-specific first, then global) ---
    debug_step(f"Reading Custom Properties (config: '{cfg_name or 'default'}')")
    props = {}

    def _read_cpm_props(cpm):
        out = {}
        if cpm is None:
            return out
        try:
            names = cpm.GetNames()
            if names and hasattr(names, "__iter__"):
                for n in names:
                    try:
                        res = cpm.Get4(n, False, "", "")
                        if isinstance(res, (tuple, list)):
                            out[n] = res[2] if len(res) > 2 else res[1]
                        else:
                            out[n] = res
                    except Exception:
                        pass
        except Exception:
            pass
        return out

    try:
        ext = safe_call(model, "Extension")
        if ext:
            # Config-specific properties first
            if cfg_name:
                props.update(_read_cpm_props(ext.CustomPropertyManager(cfg_name)))
            # Always also read global (config-independent) properties
            props.update(_read_cpm_props(ext.CustomPropertyManager("")))

        if props:
            print(f"OK ({len(props)} found)")
            for k, v in props.items():
                print(f"  {k}: {v}")
        else:
            print("OK (0 found)")
    except Exception as e:
        print(f"FAILED ({e})")

    # (Volume & Surface Area handled in unified mass-properties block above)

    # --- Components (Assembly BOM) OR Features (Part) ---
    components_list = []
    if is_assembly:
        debug_step("Iterating Assembly Components (BOM)")
        try:
            # GetComponents(False) returns all components including sub-assemblies (deep)
            comps = safe_call(assembly, "GetComponents", False)
            if comps:
                for c in comps:
                    name = safe_call(c, "Name2") or ""
                    if name:
                        components_list.append(name)
                print(f"OK ({len(components_list)} components)")
                for n in components_list[:10]:
                    print(f"  -> {n}")
                if len(components_list) > 10:
                    print(f"  ... and {len(components_list) - 10} more")
            else:
                print("OK (0 components)")
        except Exception as e:
            print(f"FAILED ({e})")
    else:
        debug_step("Counting Features")
        try:
            feat_count = 0
            feat = safe_call(model, "FirstFeature")
            while feat:
                feat_count += 1
                feat = safe_call(feat, "GetNextFeature")
            print(f"OK ({feat_count} features)")
        except Exception as e:
            print(f"FAILED ({e})")

    # --- File Information ---
    debug_step("Reading File Info")
    try:
        file_path = safe_call(model, "GetPathName")
        title = safe_call(model, "GetTitle")
        saved = safe_call(model, "IsSaved")
        print(f"OK (Path: {file_path}, Saved: {saved})")
    except Exception as e:
        print(f"FAILED ({e})")

except Exception as e:
    print(f"\n[CRITICAL ERROR] {e}")