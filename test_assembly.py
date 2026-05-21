import win32com.client
import sys
import pythoncom

pythoncom.CoInitialize()


def debug_step(msg):
    print(f"[DEBUG] {msg}...", end=" ", flush=True)


def safe_call(obj, attr_name, *args):
    if obj is None:
        return None
    try:
        attr = getattr(obj, attr_name)
        return attr(*args) if callable(attr) else attr
    except Exception:
        return None


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
    debug_step("Connecting to SOLIDWORKS")
    try:
        sw = win32com.client.GetObject(Class="SldWorks.Application")
    except Exception:
        try:
            sw = win32com.client.gencache.EnsureDispatch("SldWorks.Application")
        except Exception:
            sw = win32com.client.Dispatch("SldWorks.Application")
    sw.Visible = True
    sw.UserControl = True
    print("OK")

    debug_step("Getting Active Document")
    model_raw = safe_call(sw, "IActiveDoc2") or safe_call(sw, "ActiveDoc")

    if model_raw is None:
        PART_PATH = r"C:\mpd\models\SOLIDWORKS DATABASE\Equipment Rack\40U Rack.SLDASM"
        doc_type = 2 if PART_PATH.lower().endswith(".sldasm") else 1
        debug_step(f"No active doc, opening '{PART_PATH}'")
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

    debug_step("Casting to ModelDoc2/AssemblyDoc")
    try:
        model = win32com.client.CastTo(model_raw, "IModelDoc2")
    except Exception:
        model = model_raw

    debug_step("Checking document type")
    doc_type = safe_call(model, "GetType")
    is_assembly = (doc_type == 2)
    print(f"OK (Type: {'Assembly' if is_assembly else 'Part'} [{doc_type}])")

    try:
        assembly = win32com.client.CastTo(model_raw, "IAssemblyDoc") if is_assembly else None
    except Exception:
        assembly = model_raw if is_assembly else None
    print("OK")

    debug_step("Getting Active Configuration")
    cfg_name = ""
    try:
        cfg_mgr = safe_call(model, "ConfigurationManager")
        cfg = safe_call(cfg_mgr, "ActiveConfiguration")
        cfg_name = safe_call(cfg, "Name") or ""
    except Exception:
        cfg_name = ""
    print(f"OK ({cfg_name or '<active>'})")

    # --- Bounding Envelope ---
    debug_step("Calculating Bounding Envelope")
    try:
        box = None
        if is_assembly:
            top_comps = safe_call(assembly, "GetComponents", True)
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

        if box and len(box) >= 6:
            x1, y1, z1, x2, y2, z2 = box[:6]
            width_mm  = abs(x2 - x1) * 1000
            depth_mm  = abs(y2 - y1) * 1000
            height_mm = abs(z2 - z1) * 1000
            print(f"OK (W:{width_mm:.1f}mm x D:{depth_mm:.1f}mm x H:{height_mm:.1f}mm)")
        else:
            print("FAILED (no box data)")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Mass Properties ---
    debug_step("Extracting Mass Properties")
    mass_kg = volume_mm3 = surface_mm2 = cg_x = cg_y = cg_z = None
    try:
        mass_props = safe_call(model, "GetMassProperties")
        if mass_props and len(mass_props) >= 6:
            cg_x        = float(mass_props[0]) * 1000
            cg_y        = float(mass_props[1]) * 1000
            cg_z        = float(mass_props[2]) * 1000
            volume_mm3  = float(mass_props[3]) * 1e9
            surface_mm2 = float(mass_props[4]) * 1e6
            mass_kg     = float(mass_props[5])
    except Exception as e:
        print(f"  [debug] {e}")

    if mass_kg is not None:
        print("OK")
        print(f"  -> Mass:         {mass_kg:.4f} kg ({mass_kg*1000:.2f} grams)")
        print(f"  -> Volume:       {volume_mm3:.2f} mm³")
        print(f"  -> Surface Area: {surface_mm2:.2f} mm²")
        print(f"  -> Center of Mass (CG): X={cg_x:.2f}mm, Y={cg_y:.2f}mm, Z={cg_z:.2f}mm")
    else:
        print("FAILED (no mass data)")

    # --- Custom Properties ---
    debug_step(f"Reading Custom Properties (config: '{cfg_name or 'default'}')")
    props = {}
    try:
        ext = safe_call(model, "Extension")
        if ext:
            if cfg_name:
                props.update(_read_cpm_props(ext.CustomPropertyManager(cfg_name)))
            props.update(_read_cpm_props(ext.CustomPropertyManager("")))
        print(f"OK ({len(props)} found)")
        for k, v in props.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Assembly BOM ---
    if is_assembly:
        debug_step("Iterating Assembly Components (BOM)")
        try:
            comps = safe_call(assembly, "GetComponents", False)
            components_list = []
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
        except Exception as e:
            print(f"FAILED ({e})")

    # --- File Info ---
    debug_step("Reading File Info")
    try:
        file_path = safe_call(model, "GetPathName")
        print(f"OK (Path: {file_path})")
    except Exception as e:
        print(f"FAILED ({e})")

except Exception as e:
    print(f"\n[CRITICAL ERROR] {e}")
