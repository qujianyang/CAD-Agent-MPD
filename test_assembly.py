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
    # EnsureDispatch first — it generates Python wrappers from the SW typelib
    # so that COM methods like Extension.CreateMassProperty() are exposed.
    # GetObject alone returns a late-bound dispatch where those methods raise
    # "Member not found" (DISP_E_MEMBERNOTFOUND).
    try:
        sw = win32com.client.gencache.EnsureDispatch("SldWorks.Application")
    except Exception:
        try:
            sw = win32com.client.GetObject(Class="SldWorks.Application")
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
    # We keep BOTH the dimensions (W/D/H) and the raw min/max corners.
    # The min/max corners are used downstream to derive a base-relative CG
    # when the proper IMassProperty coord-system API is unavailable
    # (e.g. SOLIDWORKS Education Edition blocks GetCoordinateSystemTransformByName2).
    debug_step("Calculating Bounding Envelope")
    bbox_x_min = bbox_y_min = bbox_z_min = None
    bbox_x_max = bbox_y_max = bbox_z_max = None
    width_mm = depth_mm = height_mm = None
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
            # Convert m -> mm, keep min/max for base-relative CG derivation
            bbox_x_min, bbox_y_min, bbox_z_min = x1 * 1000, y1 * 1000, z1 * 1000
            bbox_x_max, bbox_y_max, bbox_z_max = x2 * 1000, y2 * 1000, z2 * 1000
            width_mm  = abs(x2 - x1) * 1000
            depth_mm  = abs(y2 - y1) * 1000
            height_mm = abs(z2 - z1) * 1000
            print(f"OK (W:{width_mm:.1f}mm x D:{depth_mm:.1f}mm x H:{height_mm:.1f}mm)")
            print(f"  -> BBox Min: X={bbox_x_min:.2f}mm Y={bbox_y_min:.2f}mm Z={bbox_z_min:.2f}mm")
            print(f"  -> BBox Max: X={bbox_x_max:.2f}mm Y={bbox_y_max:.2f}mm Z={bbox_z_max:.2f}mm")
        else:
            print("FAILED (no box data)")
    except Exception as e:
        print(f"FAILED ({e})")

    # --- Mass Properties ---
    #
    # Two paths, tried in order:
    #
    #   Path A — IMassProperty + SetCoordinateSystem (the "proper" SW API)
    #     Works on commercial SOLIDWORKS. The user can name a coordinate
    #     system feature like "Mounting_Base" at the base of the rack, and
    #     SW will compute the CG directly in that frame.
    #
    #   Path B — GetMassProperties + bounding-box-derived base offset
    #     Works on ANY SW (including Education Edition, where the
    #     IModelDocExtension dispatch methods are blocked).
    #     GetMassProperties returns CG in the default origin's frame; we
    #     then translate it to a base-relative frame using the bounding box
    #     (z_min as the floor, x/y bbox centre as the horizontal reference).
    #
    # Both paths populate cg_x_base / cg_y_base / cg_z_base (mm), which is
    # the frame the physics engine actually consumes — CG relative to the
    # rack's mounting base.
    debug_step("Extracting Mass Properties")
    mass_kg = volume_mm3 = surface_mm2 = None
    cg_x = cg_y = cg_z = None              # in coord_sys_used frame (mm)
    cg_x_base = cg_y_base = cg_z_base = None  # always base-relative (mm)
    coord_sys_used = "default"
    PREFERRED_COORD_SYSTEMS = ("Mounting_Base", "Mount_Base", "Base", "Rack_Origin")

    try:
        try:
            ext = model.Extension
        except Exception:
            ext = None

        # -------------- PATH A: IMassProperty (commercial SW) --------------
        mass_prop = None
        if ext is not None:
            for method_name in ("CreateMassProperty2", "CreateMassProperty"):
                try:
                    mp_method = getattr(ext, method_name, None)
                    if mp_method is None:
                        continue
                    candidate = mp_method()
                    if candidate is not None:
                        mass_prop = candidate
                        break
                except Exception:
                    pass

        if mass_prop is not None:
            # Try to set the output coord system to one of the preferred names.
            xform = None
            for sys_name in PREFERRED_COORD_SYSTEMS:
                try:
                    xform = ext.GetCoordinateSystemTransformByName2(sys_name)
                except Exception:
                    xform = None
                if xform is not None:
                    try:
                        if mass_prop.SetCoordinateSystem(xform):
                            coord_sys_used = sys_name
                            break
                    except Exception:
                        pass

            # If by-name didn't work, walk features and look for any CoordSys.
            if coord_sys_used == "default":
                try:
                    feat = model.FirstFeature
                    while feat is not None:
                        try:
                            ftype = feat.GetTypeName2() or feat.GetTypeName() or ""
                            fname = feat.Name or ""
                        except Exception:
                            ftype, fname = "", ""
                        if ftype == "CoordSys":
                            try:
                                xf2 = ext.GetCoordinateSystemTransformByName2(fname)
                                if xf2 is not None and mass_prop.SetCoordinateSystem(xf2):
                                    coord_sys_used = fname
                                    break
                            except Exception:
                                pass
                        try:
                            feat = feat.GetNextFeature()
                        except Exception:
                            feat = None
                except Exception:
                    pass

            # Read properties (units: kg, m^3, m^2, m).
            try:
                cg = mass_prop.CenterOfMass
                if cg and len(cg) >= 3:
                    cg_x = float(cg[0]) * 1000.0
                    cg_y = float(cg[1]) * 1000.0
                    cg_z = float(cg[2]) * 1000.0
                mass_kg     = float(mass_prop.Mass)
                volume_mm3  = float(mass_prop.Volume)      * 1e9
                surface_mm2 = float(mass_prop.SurfaceArea) * 1e6
            except Exception as e:
                print(f"  [debug] IMassProperty read failed: {e}")
                mass_kg = None  # force Path B

        # -------------- PATH B: GetMassProperties + BBOX (universal) --------------
        if mass_kg is None:
            coord_sys_used = "default (bbox-derived base)"
            mp_array = safe_call(model, "GetMassProperties")
            if mp_array and len(mp_array) >= 6:
                cg_x        = float(mp_array[0]) * 1000.0
                cg_y        = float(mp_array[1]) * 1000.0
                cg_z        = float(mp_array[2]) * 1000.0
                volume_mm3  = float(mp_array[3]) * 1e9
                surface_mm2 = float(mp_array[4]) * 1e6
                mass_kg     = float(mp_array[5])

    except Exception as e:
        print(f"  [debug] mass properties block raised: {e}")

    # -------------- Compute base-relative CG --------------
    # If Path A succeeded with a non-default coord system, the IMassProperty
    # already gave us CG in the desired frame -> use as-is.
    # If Path A fell back to default (or Path B was used), translate CG using
    # the bounding box: floor at z_min, footprint centre at (x,y) bbox-centre.
    if cg_x is not None and cg_y is not None and cg_z is not None:
        if coord_sys_used in PREFERRED_COORD_SYSTEMS or (
            coord_sys_used != "default"
            and not coord_sys_used.startswith("default")
        ):
            # CG already in the named coord system frame.
            cg_x_base, cg_y_base, cg_z_base = cg_x, cg_y, cg_z
        elif bbox_z_min is not None:
            # Derive: Z is height above the bbox floor; X/Y are offset from
            # the bbox horizontal centre (so a perfectly centred rack
            # reads cg_x_base ≈ 0).
            cg_x_base = cg_x - (bbox_x_min + bbox_x_max) / 2.0
            cg_y_base = cg_y - (bbox_y_min + bbox_y_max) / 2.0
            cg_z_base = cg_z - bbox_z_min
        else:
            # No bbox available either; leave unset.
            cg_x_base = cg_y_base = cg_z_base = None

    if mass_kg is not None:
        print("OK")
        print(f"  -> Mass:         {mass_kg:.4f} kg ({mass_kg*1000:.2f} grams)")
        print(f"  -> Volume:       {volume_mm3:.2f} mm³")
        print(f"  -> Surface Area: {surface_mm2:.2f} mm²")
        print(f"  -> Coord System: {coord_sys_used}")
        print(f"  -> Center of Mass (CG, raw): X={cg_x:.2f}mm, Y={cg_y:.2f}mm, Z={cg_z:.2f}mm")
        if cg_z_base is not None:
            print(f"  -> CG from Base:           X={cg_x_base:.2f}mm, Y={cg_y_base:.2f}mm, Z={cg_z_base:.2f}mm")
            if height_mm:
                ratio = cg_z_base / height_mm
                print(f"  -> CG Height Ratio:        {ratio*100:.1f}% of rack height ({height_mm:.0f}mm)")
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
