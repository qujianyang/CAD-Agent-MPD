"""
Streamlit UI for the CAD-Aware Shock Mount Selection Assistant.

Three tabs:
  1. Quick Selector  — Manual mass entry, no SolidWorks needed. Server-friendly.
  2. CAD + Shock     — Live SolidWorks extraction + auto-selection.
  3. Agent Chat      — Tool-calling LLM agent (NVIDIA Llama 3.1 70B).

Run locally:
    streamlit run app.py

Run on a server (LAN-accessible):
    streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""
import os
import sys
import math
import subprocess
from pathlib import Path
from dotenv import load_dotenv

import pandas as pd
import streamlit as st

from llm_config import resolve_llm_config
from cad_compliance_checker import _parse_cad_output
from physics_engine import ShockEnv, _loads_per_isolator, run_analysis, _NO_CLEARANCE_MM
from catalog import (
    ALL_CATALOGS, AUTO_SELECT_CATALOGS,
    CB61400_CATALOG, CB1400_CATALOG, CB1500_CATALOG, CB1700_CATALOG,
    select_isolator, select_and_analyze, format_selection_table, format_report,
)
from ui_selection_summary import (
    build_candidate_comparison_rows,
    build_load_case_rows,
    build_review_next_rows,
    build_shock_selection_key,
    describe_selection_key_changes,
    format_assessment_context,
    format_clearance_hint,
    readable_constraint,
    summarize_selection,
)
from ui_copy import (
    CHAT_EXPORT_TITLE,
    CLEAR_RESULT_LABEL,
    CLEAR_CHAT_LABEL,
    CLEARANCE_HELP_TEXT,
    EXPORT_HTML_LABEL,
    EXPORT_MARKDOWN_LABEL,
    FULL_PHYSICS_REPORT_LABEL,
    MAIN_TAB_LABELS,
    ROAD_VIBRATION_LABEL,
    REVIEW_NEXT_LABEL,
    SHOCK_ASSISTANT_LABEL,
    UPDATE_RESULT_LABEL,
)
from tiedown_engine import MountFace, Item, analyze_item, run_tiedown_analysis
from fastener_catalog import make_fastener, size_fasteners, BOLT_CLASSES, BOLT_SIZES, NON_BOLTS
from tiedown_import import import_workbook, WB_DEFAULT
from mobility_engine import Vehicle, Aero, run_mobility_analysis
from mobility_import import (
    vehicle_measured, vehicle_theory, approach_departure_angles,
    measurement_measured, measurement_unladen, shelter_cg, WB_DEFAULT as MB_DEFAULT,
    shelter_components, shelter_datum_offsets,
)
from mobility_scenarios import (
    vehicle_from_certified_cg, vehicle_from_wheel_loads, check_cg_plausibility,
    MassChange, apply_mass_changes, baseline_delta,
    sf_verdict, margin_for_direction, ZCG_SOURCES,
    zcg_from_tilt_tests, iso_x_to_axle_x, axle_x_to_iso_x,
    FRONT_AXLE_TO_ISO_PLANE_MM, DEFAULT_RSTAT_MM,
    OEM_MARGIN_LONGITUDINAL, OEM_MARGIN_LATERAL, OEM_MARGIN_CORNERING,
    VERDICT_UNSTABLE, VERDICT_BELOW, VERDICT_MEETS, VERDICT_STRUCTURAL,
    DEFAULT_FRONT_AXLE_LIMIT_KG, DEFAULT_REAR_AXLE_LIMIT_KG, DEFAULT_GVW_LIMIT_KG,
    derive_4axle_wheel_load_summary,
)
# T1 variant support (four-axle family): profile-driven runner + xlsx importer.
from mobility_profiles import E2_PROFILE, T1_PROFILE, get_profile
from mobility_profile_analysis import (
    run_profile_mobility_analysis, format_profile_axle_context,
)
from mobility_import_t1 import (
    vehicle_measured_t1, vehicle_theory_t1, payload_cg_from_measured_t1,
    workbook_path as t1_workbook_path, WB_DEFAULT as T1_DEFAULT,
)
from twist_lock_engine import analyze_twist_locks, format_twist_lock_report, AXES


# ----------------------------------------------------------------------------
# Page config + environment
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="CAD Safety Assistant",
    page_icon="CS",
    layout="wide",
)

from streamlit_float import float_init, float_css_helper
float_init()

load_dotenv()
try:
    LLM_CONFIG = resolve_llm_config()
    LLM_CONFIG_ERROR = ""
except ValueError as e:
    LLM_CONFIG = None
    LLM_CONFIG_ERROR = str(e)
API_KEY = LLM_CONFIG.api_key if LLM_CONFIG else ""
API_KEY_ENV = LLM_CONFIG.api_key_env if LLM_CONFIG else "OPENAI_API_KEY or NVIDIA_API_KEY"
LLM_PROVIDER = LLM_CONFIG.provider if LLM_CONFIG else "invalid"

# SolidWorks COM extraction needs Windows (pywin32 + a tkinter file dialog). On
# Linux (e.g. Streamlit Cloud) the CAD tab self-disables — see the CAD + Shock tab.
_SOLIDWORKS_AVAILABLE = (os.name == "nt")
LLM_MODEL = LLM_CONFIG.model if LLM_CONFIG else "invalid"

SERIES_MAP = {
    "All series (CB1400 + CB1500 + CB1700)":            AUTO_SELECT_CATALOGS,
    "CB1400 (1/2\" wire)":                              CB1400_CATALOG,
    "CB1500 (5/8\" wire)":                              CB1500_CATALOG,
    "CB1700 (7/8\" wire)":                              CB1700_CATALOG,
    "All incl. CB61400 (6-strand softer, opt-in)":      ALL_CATALOGS,
    "CB61400 only (6-strand 1/2\" wire)":               CB61400_CATALOG,
}

# Shock pulse profile: UI label -> physics_engine pulse_shape key.
PULSE_MAP = {
    "Saw-Tooth (terminal-peak)": "sawtooth",
    "Half-Sine (~27% harsher)":  "half_sine",
}

# Selection objective: UI label -> catalog.select_isolator objective key.
# Clearance is a hard gate in ALL modes; the objective only breaks ties among
# the parts that already pass all four cases.
OBJECTIVE_MAP = {
    "Least movement / max clearance": "max_clearance",
    "Lowest transmitted shock": "best_isolation",
}


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
def _init_state():
    defaults = {
        "cad_props":   None,
        "raw_output":  "",
        "raw_stderr":  "",
        "extract_attempted": False,
        "extract_returncode": None,
        "agent":       None,
        "chat_history": [],   # list of {"role": "user"|"assistant", "content": str}
        "tiedown_agent": None,
        "tiedown_chat_history": [],
        "mobility_agent": None,
        "mobility_chat_history": [],
        "q_selection_result": None,
        "q_selection_key": None,
        # Mobility scenario workspace
        "mb_vehicle": None,    # derived mobility Vehicle (single source of truth)
        "mb_prov": None,       # {"method": ..., "source": ...} provenance
        "mb_approach": None,   # (approach_deg, departure_deg) or None
        "mb_report": None,     # last MobilityReport (cleared on vehicle change)
        "mb_base": None,       # baseline Vehicle for modification deltas, or None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def run_solidworks_extraction(
    script: str = "test_assembly.py",
    file_path: str | None = None,
) -> tuple[dict, str, str, int]:
    """
    Run test_assembly.py in a subprocess.
    Returns (parsed props, raw stdout, raw stderr, returncode).
    If file_path is given, passes --file to the script so it opens that CAD
    file. Otherwise the script uses whatever SolidWorks document is active.
    """
    cmd = [sys.executable, script]
    if file_path:
        cmd += ["--file", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return (_parse_cad_output(result.stdout),
            result.stdout,
            result.stderr or "",
            result.returncode)


def _shock_env_widget(prefix: str) -> ShockEnv:
    """Render a shock environment input row (Ao / to / GT limit / pulse); return a ShockEnv."""
    c1, c2, c3, c4 = st.columns(4)
    Ao = c1.number_input("Shock Ao [G]",       value=20.0, min_value=1.0,  max_value=60.0,
                         step=1.0, key=f"{prefix}_Ao")
    to = c2.number_input("Pulse to [ms]",      value=11.0, min_value=1.0,  max_value=100.0,
                         step=1.0, key=f"{prefix}_to")
    GL = c3.number_input("GT limit [G]",       value=10.0, min_value=1.0,  max_value=50.0,
                         step=1.0, key=f"{prefix}_GL")
    pulse_label = c4.selectbox("Pulse profile", list(PULSE_MAP.keys()), key=f"{prefix}_pulse")
    return ShockEnv(Ao_G=Ao, to_s=to / 1000.0, GT_limit_G=GL,
                    pulse_shape=PULSE_MAP[pulse_label])


def _clearance_widget(prefix: str) -> tuple[float, float, float]:
    """Render X/Y/Z installation-clearance inputs [mm].

    Returns the per-axis gap to neighbouring equipment. A value of 0 means
    'no clearance limit' and is mapped to the sentinel so only the mount's own
    travel constrains that axis (i.e. original behaviour).
    """
    st.caption(CLEARANCE_HELP_TEXT)
    c1, c2, c3 = st.columns(3)
    cx = c1.number_input("Clearance X [mm]", value=0.0, min_value=0.0, max_value=500.0,
                         step=1.0, key=f"{prefix}_clrx")
    cy = c2.number_input("Clearance Y [mm]", value=0.0, min_value=0.0, max_value=500.0,
                         step=1.0, key=f"{prefix}_clry")
    cz = c3.number_input("Clearance Z [mm]", value=0.0, min_value=0.0, max_value=500.0,
                         step=1.0, key=f"{prefix}_clrz")
    conv = lambda v: v if v > 0 else _NO_CLEARANCE_MM
    return conv(cx), conv(cy), conv(cz)


def _layout_box_widget(prefix: str) -> tuple[float, float, float]:
    """Render manual enclosure dimensions for the mount-layout visualizer."""
    c1, c2, c3 = st.columns(3)
    width_mm = c1.number_input(
        "Width X [mm]",
        value=600.0,
        min_value=1.0,
        max_value=10000.0,
        step=50.0,
        key=f"{prefix}_layout_width",
        help="Equipment or enclosure width along the X axis.",
    )
    depth_mm = c2.number_input(
        "Depth Y [mm]",
        value=800.0,
        min_value=1.0,
        max_value=10000.0,
        step=50.0,
        key=f"{prefix}_layout_depth",
        help="Equipment or enclosure depth along the Y axis.",
    )
    height_mm = c3.number_input(
        "Height Z [mm]",
        value=1200.0,
        min_value=1.0,
        max_value=10000.0,
        step=50.0,
        key=f"{prefix}_layout_height",
        help="Equipment or enclosure height along the Z axis.",
    )
    return float(width_mm), float(depth_mm), float(height_mm)


def _wall_face_widget(prefix: str) -> str:
    """Choose the vertical face used for wall mounts in the layout drawing."""
    return st.selectbox(
        "Wall mount face for drawing",
        ["back", "front", "left", "right"],
        index=0,
        key=f"{prefix}_layout_wall_face",
        format_func=lambda v: {
            "back": "Back face (+Y)",
            "front": "Front face (-Y)",
            "left": "Left face (-X)",
            "right": "Right face (+X)",
        }[v],
        help="Only affects the visual layout. Shock calculations still use the bottom/wall mount counts.",
    )


def _layout_box_from_cad_props(props) -> tuple[float, float, float] | None:
    """Extract positive W/D/H dimensions from SolidWorks properties."""
    if not props:
        return None
    try:
        width_mm = float(props.get("width_mm"))
        depth_mm = float(props.get("depth_mm"))
        height_mm = float(props.get("height_mm"))
    except (TypeError, ValueError):
        return None
    if width_mm <= 0 or depth_mm <= 0 or height_mm <= 0:
        return None
    return width_mm, depth_mm, height_mm


def _clearance_hint_candidate(
    *,
    mass_kg: float,
    n_bottom: int,
    n_wall: int,
    env: ShockEnv,
    catalog,
    objective: str = "max_clearance",
):
    """Return the no-clearance valid candidate used to estimate required movement."""
    loads = _loads_per_isolator(mass_kg, n_bottom, n_wall)
    candidates = select_isolator(
        m_comp_bottom_kg=loads["m_comp_bottom_kg"],
        m_comp_wall_kg=loads["m_comp_wall_kg"],
        m_roll_wall_kg=loads["m_roll_wall_kg"],
        m_roll_bottom_kg=loads["m_roll_bottom_kg"],
        env=env,
        catalog=catalog,
        clr_x_mm=_NO_CLEARANCE_MM,
        clr_y_mm=_NO_CLEARANCE_MM,
        clr_z_mm=_NO_CLEARANCE_MM,
        objective=objective,
    )
    return next((candidate for candidate in candidates if candidate.valid), None)


def _objective_widget(prefix: str) -> str:
    """Render the selection-objective selectbox; return the catalog objective key."""
    label = st.selectbox(
        "Selection objective",
        list(OBJECTIVE_MAP.keys()),
        key=f"{prefix}_obj",
        help="Clearance is a hard pass/fail gate in every mode. This only chooses "
             "between parts that already pass all 4 cases.",
    )
    return OBJECTIVE_MAP[label]


def _mount_widget(prefix: str, default_bot: int = 6, default_wall: int = 4) -> tuple[int, int]:
    c1, c2 = st.columns(2)
    n_bot  = c1.number_input("n_bottom (bottom mounts)", value=default_bot,
                             min_value=2, max_value=24, step=1, key=f"{prefix}_nb")
    n_wall = c2.number_input("n_wall   (wall mounts)",   value=default_wall,
                             min_value=2, max_value=24, step=1, key=f"{prefix}_nw")
    return int(n_bot), int(n_wall)


def _browse_cad_file() -> str | None:
    """Open a native Windows file-explorer dialog; return selected path or None."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select SolidWorks Assembly or Part",
        filetypes=[
            ("SolidWorks files", "*.SLDASM *.SLDPRT"),
            ("SolidWorks Assembly", "*.SLDASM"),
            ("SolidWorks Part", "*.SLDPRT"),
            ("All files", "*.*"),
        ],
        initialdir=r"C:\mpd\models\SOLIDWORKS DATABASE",
    )
    root.destroy()
    return path.replace("/", "\\") if path else None


def _export_text(chat_history: list[dict]) -> str:
    from datetime import datetime
    lines = [
        CHAT_EXPORT_TITLE,
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]
    for msg in chat_history:
        role = "USER" if msg["role"] == "user" else "ASSISTANT"
        lines.append(f"[{role}]")
        for ev in msg.get("events") or []:
            if ev["type"] == "tool_call":
                args_str = ", ".join(f"{k}={v!r}" for k, v in ev["args"].items())
                lines.append(f"  >> Tool: {ev['name']}({args_str})")
            elif ev["type"] == "tool_result":
                preview = ev["content"][:400] + ("..." if len(ev["content"]) > 400 else "")
                lines.append(f"  << Result: {preview}")
        lines.append(msg["content"])
        lines.append("")
    return "\n".join(lines)


def _export_markdown(chat_history: list[dict]) -> str:
    from datetime import datetime
    lines = [
        f"# {CHAT_EXPORT_TITLE}",
        f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "---",
        "",
    ]
    for msg in chat_history:
        if msg["role"] == "user":
            lines.append("### User")
            lines.append(msg["content"])
        else:
            lines.append("### Assistant")
            events = msg.get("events") or []
            tool_events = [e for e in events if e["type"] in ("tool_call", "tool_result")]
            if tool_events:
                lines.append("<details>")
                lines.append("<summary>Agent steps</summary>")
                lines.append("")
                for ev in tool_events:
                    if ev["type"] == "tool_call":
                        args_str = "\n".join(f"  {k} = {v!r}" for k, v in ev["args"].items())
                        lines.append(f"**Tool call: `{ev['name']}`**")
                        lines.append(f"```python\n{args_str or '(no args)'}\n```")
                    elif ev["type"] == "tool_result":
                        preview = ev["content"][:600] + ("..." if len(ev["content"]) > 600 else "")
                        lines.append(f"**Result from `{ev['name']}`**")
                        lines.append(f"```\n{preview}\n```")
                lines.append("</details>")
                lines.append("")
            lines.append(msg["content"])
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _export_html(chat_history: list[dict]) -> str:
    from datetime import datetime
    import html as _html

    def esc(s: str) -> str:
        return _html.escape(str(s))

    rows = []
    for msg in chat_history:
        if msg["role"] == "user":
            rows.append(
                f'<div class="msg user"><div class="label">User</div>'
                f'<div class="content">{esc(msg["content"])}</div></div>'
            )
        else:
            events = msg.get("events") or []
            tool_html = ""
            tool_events = [e for e in events if e["type"] in ("tool_call", "tool_result")]
            if tool_events:
                steps = []
                for ev in tool_events:
                    if ev["type"] == "tool_call":
                        args_str = "\n".join(f"  {k} = {v!r}" for k, v in ev["args"].items())
                        steps.append(
                            f'<div class="step"><b>Tool call: <code>{esc(ev["name"])}</code></b>'
                            f'<pre>{esc(args_str or "(no args)")}</pre></div>'
                        )
                    elif ev["type"] == "tool_result":
                        preview = ev["content"][:600] + ("..." if len(ev["content"]) > 600 else "")
                        steps.append(
                            f'<div class="step"><b>Result from <code>{esc(ev["name"])}</code></b>'
                            f'<pre>{esc(preview)}</pre></div>'
                        )
                tool_html = (
                    f'<details class="trace"><summary>Agent steps ({len(tool_events)})</summary>'
                    + "".join(steps)
                    + "</details>"
                )
            rows.append(
                f'<div class="msg assistant"><div class="label">Assistant</div>'
                f'{tool_html}<div class="content">{esc(msg["content"])}</div></div>'
            )

    body = "\n".join(rows)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{CHAT_EXPORT_TITLE}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #f8f9fa; color: #212529; }}
  h1 {{ font-size: 1.4em; border-bottom: 2px solid #dee2e6; padding-bottom: 8px; }}
  .ts {{ color: #6c757d; font-size: 0.85em; margin-bottom: 24px; }}
  .msg {{ margin-bottom: 20px; border-radius: 8px; padding: 14px 18px; }}
  .msg.user {{ background: #e7f3ff; border-left: 4px solid #0d6efd; }}
  .msg.assistant {{ background: #fff; border: 1px solid #dee2e6; border-left: 4px solid #198754; }}
  .label {{ font-weight: 700; font-size: 0.8em; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; color: #6c757d; }}
  .content {{ white-space: pre-wrap; line-height: 1.6; }}
  details.trace {{ margin-bottom: 10px; background: #f1f3f5; border-radius: 6px; padding: 8px 12px; font-size: 0.88em; }}
  details.trace summary {{ cursor: pointer; font-weight: 600; color: #495057; }}
  .step {{ margin-top: 8px; }}
  pre {{ background: #212529; color: #f8f9fa; border-radius: 4px; padding: 8px; overflow-x: auto; font-size: 0.82em; white-space: pre-wrap; }}
  code {{ background: #e9ecef; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>{CHAT_EXPORT_TITLE}</h1>
<p class="ts">Exported: {ts}</p>
{body}
</body>
</html>"""


def _render_mount_layout_panel(
    rec,
    *,
    layout_box_mm: tuple[float, float, float] | None,
    clearances: tuple[float, float, float],
    n_bottom: int,
    n_wall: int,
    wall_face: str,
):
    """Render deterministic Layer 1 mount layout for the selected candidate."""
    if not layout_box_mm:
        return

    from mount_layout_viz import build_layout_figure, layout_summary

    width_mm, depth_mm, height_mm = layout_box_mm
    summary = layout_summary(
        width_mm,
        depth_mm,
        height_mm,
        n_bottom,
        n_wall,
        deflections=rec,
        clearances=clearances,
        wall_face=wall_face,
    )
    fig = build_layout_figure(
        width_mm,
        depth_mm,
        height_mm,
        n_bottom,
        n_wall,
        deflections=rec,
        clearances=clearances,
        wall_face=wall_face,
        title=f"{rec.entry.part_no}: {n_bottom} bottom + {n_wall} wall mounts",
    )
    fig.update_layout(height=460)

    with st.expander("Mount layout and movement envelope", expanded=True):
        st.caption(
            "Deterministic drawing from the selected part and your inputs. "
            "Blue markers are bottom mounts, orange markers are wall mounts, "
            "green/red dotted box is the shock movement envelope, and grey box "
            "is the entered clearance envelope."
        )
        st.plotly_chart(fig, config={"displaylogo": False})

        box = summary["box_mm"]
        sway = summary["sway_mm"]
        st.caption(
            f"Box: {box['width']:.0f} x {box['depth']:.0f} x {box['height']:.0f} mm. "
            f"Dynamic sway: X {sway['X']:.1f} mm, Y {sway['Y']:.1f} mm, "
            f"Z {sway['Z']:.1f} mm. Wall mounts shown on the {wall_face} face."
        )
        if summary["any_interference"]:
            st.error(
                "Movement envelope exceeds at least one entered clearance. "
                "Increase clearance, add mounts, or choose a stiffer/larger part."
            )


def _render_selection_result(
    report,
    candidates,
    *,
    layout_box_mm: tuple[float, float, float] | None = None,
    clearances: tuple[float, float, float] | None = None,
    wall_face: str = "back",
):
    """Render the selection result section: recommended part, then per-case table."""
    valid = [c for c in candidates if c.valid]
    rec   = valid[0] if valid else None
    summary = summarize_selection(candidates)
    clearances = clearances or (_NO_CLEARANCE_MM, _NO_CLEARANCE_MM, _NO_CLEARANCE_MM)

    if rec:
        directions = [rec.comp_bottom, rec.comp_wall, rec.roll_wall, rec.roll_bottom]
        worst_gt = max(directions, key=lambda d: d.GT_G / d.GT_limit)
        worst_movement = max(directions, key=lambda d: d.delta_mm / d.delta_limit_mm)

        with st.container(border=True):
            st.success(summary.headline)
            st.caption(summary.support_line)
            st.caption(
                "Assessed setup: " + format_assessment_context(
                    mass_kg=report.mass_kg,
                    n_bottom=report.n_bottom,
                    n_wall=report.n_wall,
                    Ao_G=report.shock_env.Ao_G,
                    to_s=report.shock_env.to_s,
                    GT_limit_G=report.shock_env.GT_limit_G,
                    pulse_shape=report.shock_env.pulse_shape,
                )
            )

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Recommended part", rec.entry.part_no, rec.entry.series)
            m2.metric(
                "Closest-to-fail check",
                f"{summary.limiting_util_pct}% of allowed",
                readable_constraint(summary.limiting_constraint),
                delta_color="off",
            )
            m3.metric(
                "Worst transmitted shock",
                f"{worst_gt.GT_G:.2f} / {worst_gt.GT_limit:.1f} G",
                f"{summary.worst_gt_pct}% of allowed",
                delta_color="off",
            )
            m4.metric(
                "Worst movement",
                f"{worst_movement.delta_mm:.1f} / {worst_movement.delta_limit_mm:.1f} mm",
                f"{summary.worst_delta_pct}% of allowed",
                delta_color="off",
            )
            if rec.static_rating_daN is not None:
                m5.metric(
                    "Static load / mount",
                    f"{rec.static_load_daN * 0.01:.2f} / {rec.static_rating_daN * 0.01:.2f} kN",
                    f"{rec.static_util:.0%} of rating",
                    delta_color="off",
                )
            else:
                m5.metric("Static load / mount", f"{rec.static_load_daN * 0.01:.2f} kN", "vendor check")
            st.caption(
                "GT is transmitted shock in G. Values are actual / allowed; below 100% passes. "
                "Static load is shown in kN; catalog daN values are converted with 1 daN = 10 N."
            )
            if summary.static_status == "unrated":
                st.warning(summary.static_text)
            st.markdown(f"**{REVIEW_NEXT_LABEL}**")
            st.table(build_review_next_rows(summary))

        k1, k2, k3 = st.columns(3)
        k1.metric("Compression K", f"{rec.entry.k_comp_lbin} lb/in")
        k2.metric("Shear K", f"{rec.entry.k_shear_lbin} lb/in")
        k3.metric("Package size", f"H={rec.entry.H_in}\" W={rec.entry.W_in}\"")
    else:
        st.error(summary.headline)
        st.caption(summary.support_line)
        st.caption(
            "Assessed setup: " + format_assessment_context(
                mass_kg=report.mass_kg,
                n_bottom=report.n_bottom,
                n_wall=report.n_wall,
                Ao_G=report.shock_env.Ao_G,
                to_s=report.shock_env.to_s,
                GT_limit_G=report.shock_env.GT_limit_G,
                pulse_shape=report.shock_env.pulse_shape,
            )
        )
        st.markdown(f"**{REVIEW_NEXT_LABEL}**")
        st.table(build_review_next_rows(summary))

    # 4-case table for the recommended part
    if rec:
        st.subheader("4 Load Cases (all must pass)")
        st.dataframe(build_load_case_rows(rec), width="stretch", hide_index=True)
        st.caption("**Binding** = the constraint closest to failing in each case. "
                   "`deflection (clearance)` means the neighbouring-equipment gap — "
                   "not the mount's own travel — is the limiting factor.")
        _render_mount_layout_panel(
            rec,
            layout_box_mm=layout_box_mm,
            clearances=clearances,
            n_bottom=report.n_bottom,
            n_wall=report.n_wall,
            wall_face=wall_face,
        )

    # Road-vibration check for the recommended part (vendor Vibration Average K)
    if rec and rec.entry.k_vib_comp_lbin is not None:
        from vibration_engine import vibration_check_for_entry
        vib = vibration_check_for_entry(rec.entry, rec.comp_bottom.m_kg)
        if vib:
            vibration_state = "isolating" if vib.attenuation < 1 else "amplifying"
            with st.expander(f"Road vibration: {vibration_state}",
                             expanded=vib.resonance_flag or vib.attenuation >= 1):
                if vib.attenuation < 1:
                    reduction_pct = (1.0 - vib.attenuation) * 100.0
                    st.success(
                        f"This mount reduces continuous road vibration by about "
                        f"{reduction_pct:.0f}%."
                    )
                    st.write(
                        f"The equipment sees {vib.grms_out:.2f} g RMS instead of "
                        f"the {vib.grms_in:.2f} g RMS chassis input."
                    )
                    st.caption(
                        "This vibration check is acceptable on transfer ratio. "
                        "Keep reviewing the shock load cases because shock and "
                        "road vibration are separate checks."
                    )
                else:
                    amplification_pct = (vib.attenuation - 1.0) * 100.0
                    st.warning(
                        f"This mount amplifies continuous road vibration by about "
                        f"{amplification_pct:.0f}%."
                    )
                    st.write(
                        f"The equipment sees {vib.grms_out:.2f} g RMS from "
                        f"the {vib.grms_in:.2f} g RMS chassis input."
                    )

                v1, v2, v3 = st.columns(3)
                v1.metric("Natural frequency", f"{vib.fn_Hz:.1f} Hz")
                v1.caption(
                    "Mounted system vibration frequency using vendor vibration "
                    "stiffness."
                )
                v2.metric("Equipment vibration", f"{vib.grms_out:.2f} g RMS")
                v2.caption(f"From {vib.grms_in:.2f} g RMS chassis input.")
                v3.metric("Transfer ratio", f"{vib.attenuation:.2f}x",
                          vibration_state,
                          delta_color="off")
                v3.caption(
                    f"Below 1.0 means isolation; output is "
                    f"{vib.attenuation * 100.0:.0f}% of input."
                )

                st.info(
                    "Interpretation: a transfer ratio below 1.0 means the mount "
                    "reduces vibration; above 1.0 means it amplifies vibration. "
                    "Natural frequency is used to check resonance risk. This "
                    "does not prove the equipment survives vibration unless an "
                    "equipment vibration limit is provided."
                )

                if vib.resonance_flag:
                    st.warning(
                        f"Resonance risk: this mount's vibration natural frequency "
                        f"({vib.fn_Hz:.1f} Hz) sits on a dominant band of the truck "
                        f"chassis PSD (peak 3.6 to 4.3 Hz). Shock performance is fine, "
                        f"but sustained road vibration will be amplified (Q about "
                        f"{1/(2*vib.zeta):.0f}). Consider a stiffer part or verify "
                        f"with the vendor."
                    )
                with st.expander("Calculation details"):
                    st.caption(
                        f"{ROAD_VIBRATION_LABEL}: method per SPF_Vibration.xls: "
                        "damped transmissibility "
                        "(zeta=0.12) over the heavy-duty-truck chassis PSD, using the "
                        "vendor's Vibration Average K (small-amplitude stiffness)."
                    )

    # Full catalog comparison
    with st.expander("Catalog comparison"):
        st.dataframe(
            build_candidate_comparison_rows(candidates),
            width="stretch",
            hide_index=True,
        )
        with st.expander("Raw selection matrix"):
            st.code(format_selection_table(candidates), language="text")

    # Physics report
    with st.expander(FULL_PHYSICS_REPORT_LABEL):
        st.code(format_report(report), language="text")


# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.title("CAD Safety Assistant")
st.caption(
    "Shock isolation, tie-down, and mobility checks for vehicle-mounted equipment."
)

if LLM_CONFIG_ERROR:
    st.warning(
        f"Assistant provider config error: {LLM_CONFIG_ERROR} "
        "Calculators and report generators still work."
    )
elif not API_KEY:
    st.warning(
        f"`{API_KEY_ENV}` not set in your environment / `.env` file. "
        "All calculators and report generators work without it; "
        "only the in-tab **assistants** require it."
    )


# ----------------------------------------------------------------------------
# Per-tab scoped assistant (collapsible widget)
# ----------------------------------------------------------------------------
@st.cache_resource
def _get_domain_agent(domain: str, provider: str, model: str, key: str):
    """One cached agent per domain (~4 tools each → reliable routing)."""
    from agent import build_agent
    return build_agent(domain, key)


def render_domain_assistant(domain: str, title: str, placeholder: str,
                            *, expanded: bool = False,
                            capabilities=None, examples=None):
    """
    Collapsible, domain-scoped chat assistant embedded in a tab.
    Each instance carries only its own domain's tools, so routing is far more
    reliable than one 14-tool co-pilot. Uses per-domain session + widget keys.

    Optional `capabilities` (a list of {capability, purpose, example, tool} dicts)
    renders a "what can this do?" popover BEFORE the API-key check, so the guide is
    visible even when the assistant is disabled. Optional `examples` renders static
    prompt suggestions just above the chat input.
    """
    hist_key = f"asst_{domain}_history"
    if hist_key not in st.session_state:
        st.session_state[hist_key] = []

    with st.expander(title, expanded=expanded):
        if capabilities:
            with st.popover("ℹ️ What can this assistant do?", width="content"):
                st.markdown(
                    "| Capability | Purpose | Example question |\n|---|---|---|\n" +
                    "\n".join(
                        f"| **{c['capability']}** | {c['purpose']} | _{c['example']}_ |"
                        for c in capabilities)
                )
                st.caption("Internal tools: " +
                           ", ".join(f"`{c['tool']}`" for c in capabilities))
        if not API_KEY:
            st.info(f"Set `{API_KEY_ENV}` in `.env` to enable the assistant.")
            return
        try:
            agent_obj = _get_domain_agent(
                domain, LLM_PROVIDER, LLM_MODEL, API_KEY)
        except Exception as e:
            st.error(f"Failed to initialize assistant: {e}")
            return

        def _trace(events):
            if not events:
                return
            with st.expander(f"🔎 {len(events)} agent steps", expanded=False):
                for i, ev in enumerate(events, 1):
                    if ev["type"] == "reasoning":
                        st.markdown(f"**{i}. 💭 Reasoning**\n\n> {ev['content']}")
                    elif ev["type"] == "tool_call":
                        args = "\n".join(f"  {k} = {v!r}" for k, v in ev["args"].items())
                        st.markdown(f"**{i}. 🔧 `{ev['name']}`**")
                        st.code(args or "(no args)", language="python")
                    elif ev["type"] == "tool_result":
                        c = ev["content"]
                        c = c if len(c) <= 800 else c[:800] + f"\n… ({len(ev['content'])-800} more)"
                        st.markdown(f"**{i}. ✅ result from `{ev['name']}`**")
                        st.code(c, language="text")

        for msg in st.session_state[hist_key]:
            with st.chat_message(msg["role"]):
                if msg.get("events"):
                    _trace(msg["events"])
                st.markdown(msg["content"])

        if examples:
            st.caption("Try:  •  " + "  •  ".join(examples))
        q = st.chat_input(placeholder, key=f"asst_{domain}_input")
        if q:
            st.session_state[hist_key].append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
            hist = [("human" if m["role"] == "user" else "ai", m["content"])
                    for m in st.session_state[hist_key][:-1]]
            with st.chat_message("assistant"):
                collected, final_text = [], ""
                with st.status("Working…", expanded=True) as status:
                    try:
                        for ev in agent_obj.stream(q, chat_history=hist or None):
                            if ev["type"] == "reasoning":
                                st.markdown(f"💭 *{ev['content']}*"); collected.append(ev)
                            elif ev["type"] == "tool_call":
                                ap = ", ".join(f"{k}={v!r}" for k, v in ev["args"].items())
                                ap = ap if len(ap) <= 120 else ap[:120] + "…"
                                st.markdown(f"🔧 **`{ev['name']}`**({ap})"); collected.append(ev)
                            elif ev["type"] == "tool_result":
                                c = ev["content"]
                                c = c if len(c) <= 400 else c[:400] + f"… ({len(ev['content'])-400} more)"
                                st.markdown(f"✅ `{ev['name']}` returned:"); st.code(c, language="text")
                                collected.append(ev)
                            elif ev["type"] == "final":
                                final_text = ev["content"]
                        status.update(
                            label=f"Done — {len([e for e in collected if e['type']=='tool_call'])} tool call(s)",
                            state="complete", expanded=False)
                    except Exception as e:
                        final_text = f"Agent error: {e}"
                        status.update(label="Failed", state="error", expanded=True)
                if final_text:
                    st.markdown(final_text)
            st.session_state[hist_key].append(
                {"role": "assistant", "content": final_text, "events": collected})

        if st.session_state[hist_key]:
            from assistant_export import history_to_markdown, history_to_html
            from datetime import datetime as _dt
            _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            _doc_title = f"{title} - chat export"
            ex1, ex2, ex3 = st.columns(3)
            ex1.download_button(
                EXPORT_MARKDOWN_LABEL,
                data=history_to_markdown(st.session_state[hist_key], title=_doc_title),
                file_name=f"{domain}_chat_{_ts}.md", mime="text/markdown",
                key=f"asst_{domain}_dl_md", width="stretch")
            ex2.download_button(
                EXPORT_HTML_LABEL,
                data=history_to_html(st.session_state[hist_key], title=_doc_title),
                file_name=f"{domain}_chat_{_ts}.html", mime="text/html",
                key=f"asst_{domain}_dl_html", width="stretch")
            if ex3.button(CLEAR_CHAT_LABEL, key=f"asst_{domain}_clear",
                          width="stretch"):
                st.session_state[hist_key] = []
                st.rerun()


def render_floating_assistant(domain: str, title: str, placeholder: str,
                              *, quickstart=None):
    """
    Floating corner chat bubble (Tidio-style) for one domain, via streamlit-float.
    Collapsed = a 💬 button bottom-right; expanded = a chat panel.
    Same domain-scoped agent as the expander version (~4 tools).

    Optional `quickstart` is a list of (label, seed_question) tuples. When the panel
    is open and the chat is empty, the labels render as buttons that seed the question
    into the same submit path as typing it.
    """
    open_key = f"float_{domain}_open"
    hist_key = f"asst_{domain}_history"
    pend_key = f"float_{domain}_pending"
    st.session_state.setdefault(open_key, False)
    st.session_state.setdefault(hist_key, [])

    box = st.container()
    with box:
        if not st.session_state[open_key]:
            # collapsed -> round button
            if st.button("💬", key=f"float_{domain}_btn", help=title):
                st.session_state[open_key] = True
                st.rerun()
            css = float_css_helper(
                width="56px", height="56px", bottom="24px", right="24px",
                css="border-radius:50%; box-shadow:0 4px 14px rgba(0,0,0,.4);",
            )
        else:
            hc1, hc2 = st.columns([5, 1])
            hc1.markdown(f"**{title}**")
            if hc2.button("X", key=f"float_{domain}_close"):
                st.session_state[open_key] = False
                st.rerun()

            if not API_KEY:
                st.info(f"Set `{API_KEY_ENV}` in `.env` to enable.")
            else:
                try:
                    agent_obj = _get_domain_agent(
                        domain, LLM_PROVIDER, LLM_MODEL, API_KEY)
                except Exception as e:
                    st.error(f"Init failed: {e}")
                    agent_obj = None

                for msg in st.session_state[hist_key]:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                if agent_obj and not st.session_state[hist_key] and quickstart:
                    st.caption("Quick start:")
                    for i, (label, seed) in enumerate(quickstart):
                        if st.button(label, key=f"float_{domain}_qs{i}",
                                     width="stretch"):
                            st.session_state[pend_key] = seed
                            st.rerun()

                q = st.chat_input(placeholder, key=f"float_{domain}_input") if agent_obj else None
                q = q or st.session_state.pop(pend_key, None)
                if q:
                    st.session_state[hist_key].append({"role": "user", "content": q})
                    with st.chat_message("user"):
                        st.markdown(q)
                    hist = [("human" if m["role"] == "user" else "ai", m["content"])
                            for m in st.session_state[hist_key][:-1]]
                    with st.chat_message("assistant"):
                        final_text = ""
                        with st.status("Working...", expanded=False) as status:
                            try:
                                for ev in agent_obj.stream(q, chat_history=hist or None):
                                    if ev["type"] == "tool_call":
                                        st.markdown(f"`{ev['name']}`")
                                    elif ev["type"] == "final":
                                        final_text = ev["content"]
                                status.update(label="Done", state="complete")
                            except Exception as e:
                                final_text = f"Agent error: {e}"
                                status.update(label="Failed", state="error")
                        if final_text:
                            st.markdown(final_text)
                    st.session_state[hist_key].append(
                        {"role": "assistant", "content": final_text})
                    st.rerun()
            css = float_css_helper(
                width="380px", height="560px", bottom="24px", right="24px",
                css="padding:14px 16px; border-radius:14px; overflow-y:auto; "
                    "background-color:#1a1d24; "
                    "border:1px solid rgba(255,255,255,.25); "
                    "box-shadow:0 8px 32px rgba(0,0,0,.6); "
                    "z-index:9999;",
            )
    box.float(css)




# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_quick, tab_cad, tab_tiedown, tab_mobility = st.tabs([
    *MAIN_TAB_LABELS,
])


# =============================================================================
# TAB 1 — Quick Selector (manual entry, server-friendly, no SolidWorks needed)
# =============================================================================
with tab_quick:
    st.subheader("Isolator Selector")
    st.caption("Enter weights directly. Useful when SolidWorks isn't running "
               "or you're working from spec sheets.")

    sel_mode = st.radio(
        "Mode",
        ["Auto (recommend best part)", "Manual (verify a specific part)"],
        horizontal=True,
        key="q_sel_mode",
    )

    st.markdown("**Weights**")
    w1, w2, w3 = st.columns([1, 1, 1])
    with w1:
        equip_kg = st.number_input("Equipment weight [kg]", value=750.0, min_value=0.0,
                                   max_value=10000.0, step=10.0, key="q_equip",
                                   help="Network gear / payload mounted on the shelf.")
    with w2:
        rack_kg = st.number_input("Rack / chassis weight [kg]", value=100.0, min_value=0.0,
                                  max_value=10000.0, step=10.0, key="q_rack",
                                  help="Frame / enclosure weight.")
    mass_kg = equip_kg + rack_kg
    with w3:
        if sel_mode == "Auto (recommend best part)":
            series_label = st.selectbox("Catalog filter", list(SERIES_MAP.keys()), key="q_series")
        else:
            all_part_options = {e.part_no: e for e in ALL_CATALOGS}
            chosen_part_no = st.selectbox(
                "Select part to verify",
                list(all_part_options.keys()),
                index=list(all_part_options.keys()).index("CB1400-15"),
                key="q_manual_part",
            )
    st.caption(f"Total system mass **M = {mass_kg:.1f} kg** (equipment + rack), "
               "distributed M/n across mounts.")

    if sel_mode == "Auto (recommend best part)":
        objective = _objective_widget("q")

    st.markdown("**Mount configuration**")
    n_bot, n_wall = _mount_widget("q", default_bot=6, default_wall=4)
    wall_face = _wall_face_widget("q")

    st.markdown("**Enclosure dimensions for layout**")
    layout_box_mm = _layout_box_widget("q")

    st.markdown("**Shock environment**")
    env = _shock_env_widget("q")

    st.markdown("**Installation clearance**")
    clr_x, clr_y, clr_z = _clearance_widget("q")
    if sel_mode == "Auto (recommend best part)":
        hint_candidate = _clearance_hint_candidate(
            mass_kg=mass_kg,
            n_bottom=n_bot,
            n_wall=n_wall,
            env=env,
            catalog=SERIES_MAP[series_label],
            objective=objective,
        )
    else:
        hint_candidate = _clearance_hint_candidate(
            mass_kg=mass_kg,
            n_bottom=n_bot,
            n_wall=n_wall,
            env=env,
            catalog=[all_part_options[chosen_part_no]],
        )
    if hint_candidate:
        st.info(format_clearance_hint(hint_candidate))

    q_selection_key = build_shock_selection_key(
        mode=sel_mode,
        mass_kg=mass_kg,
        n_bottom=n_bot,
        n_wall=n_wall,
        Ao_G=env.Ao_G,
        to_s=env.to_s,
        GT_limit_G=env.GT_limit_G,
        pulse_shape=env.pulse_shape,
        clr_x_mm=clr_x,
        clr_y_mm=clr_y,
        clr_z_mm=clr_z,
        catalog_label=series_label if sel_mode == "Auto (recommend best part)" else None,
        objective=objective if sel_mode == "Auto (recommend best part)" else None,
        part_no=None if sel_mode == "Auto (recommend best part)" else chosen_part_no,
    )

    def _run_quick_selector():
        if sel_mode == "Auto (recommend best part)":
            with st.spinner("Running 4-case selection..."):
                return select_and_analyze(
                    mass_kg   = mass_kg,
                    n_bottom  = n_bot,
                    n_wall    = n_wall,
                    cad_props = None,
                    shock_env = env,
                    catalog   = SERIES_MAP[series_label],
                    clr_x_mm  = clr_x,
                    clr_y_mm  = clr_y,
                    clr_z_mm  = clr_z,
                    objective = objective,
                )

        with st.spinner("Computing 4 load cases..."):
            entry = all_part_options[chosen_part_no]
            loads = _loads_per_isolator(mass_kg, n_bot, n_wall)
            candidates = select_isolator(
                m_comp_bottom_kg = loads["m_comp_bottom_kg"],
                m_comp_wall_kg   = loads["m_comp_wall_kg"],
                m_roll_wall_kg   = loads["m_roll_wall_kg"],
                m_roll_bottom_kg = loads["m_roll_bottom_kg"],
                env              = env,
                catalog          = [entry],
                clr_x_mm         = clr_x,
                clr_y_mm         = clr_y,
                clr_z_mm         = clr_z,
            )
            report = run_analysis(
                mass_kg, n_bot, n_wall,
                shock_env = env,
                isolator  = entry.to_isolator_spec(),
                clr_x_mm  = clr_x,
                clr_y_mm  = clr_y,
                clr_z_mm  = clr_z,
            )
            return report, candidates

    btn_label = "Select best isolator" if sel_mode == "Auto (recommend best part)" else "Run analysis"
    if st.button(btn_label, type="primary", width="stretch", key="q_run"):
        report, candidates = _run_quick_selector()
        st.session_state.q_selection_result = (report, candidates)
        st.session_state.q_selection_key = q_selection_key

    if st.session_state.q_selection_result:
        if st.session_state.q_selection_key != q_selection_key:
            changed_text = describe_selection_key_changes(
                st.session_state.q_selection_key,
                q_selection_key,
            )
            st.warning(
                f"{changed_text} Run the selection again to refresh the result."
            )
            stale_left, stale_right, _ = st.columns([1, 1, 4])
            if stale_left.button(
                UPDATE_RESULT_LABEL,
                type="primary",
                width="stretch",
                key="q_update_result",
            ):
                report, candidates = _run_quick_selector()
                st.session_state.q_selection_result = (report, candidates)
                st.session_state.q_selection_key = q_selection_key
                st.rerun()
            if stale_right.button(
                CLEAR_RESULT_LABEL,
                width="stretch",
                key="q_clear_result",
            ):
                st.session_state.q_selection_result = None
                st.session_state.q_selection_key = None
                st.rerun()
        stored_report, stored_candidates = st.session_state.q_selection_result
        _render_selection_result(
            stored_report,
            stored_candidates,
            layout_box_mm=layout_box_mm,
            clearances=(clr_x, clr_y, clr_z),
            wall_face=wall_face,
        )

    # ---- Shock-isolation assistant (collapsible, consistent with other tabs) ----
    from agent import SHOCK_CAPABILITIES
    render_domain_assistant(
        "shock_mount",
        SHOCK_ASSISTANT_LABEL,
        "e.g. 'select an isolator for a 1500 kg rack, 6 bottom + 4 wall'",
        capabilities=SHOCK_CAPABILITIES,
        examples=[c["example"] for c in SHOCK_CAPABILITIES[:5]],
    )

    render_floating_assistant(
        "ui_guide_shock",
        "Shock Selector UI Guide",
        "e.g. 'what does the Binding column mean?'",
        quickstart=[
            ("How to use shock selector", "How do I use the shock isolator selector from start to finish?"),
            ("What to do first", "What should I do first to select or verify an isolator?"),
            ("Required inputs", "What inputs do I need before running shock isolator selection?"),
            ("Form or assistant", "When should I use Auto/Manual mode, and when should I ask the shock assistant?"),
            ("Read results", "How do I read the recommended part, GT, deflection, and load-case results?"),
        ],
    )



# =============================================================================
# TAB 2 — CAD + Shock (live SolidWorks extraction + auto-selection)
# =============================================================================
with tab_cad:
    st.subheader("Live SolidWorks → Physics → Catalog")
    st.caption("Extract mass + bounding box + CG from the active SolidWorks assembly, "
               "then automatically run the 4-case selection.")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("**CAD source**")
        if not _SOLIDWORKS_AVAILABLE:
            st.info(
                "🪟 SolidWorks CAD extraction is only available on Windows. "
                "On Streamlit Cloud, use the **Shock selector** tab or enter the mass "
                "manually."
            )
        cad_mode = st.radio(
            "Where to extract from:",
            ["Use active SolidWorks document", "Specify a file path"],
            key="cad_source_mode",
            horizontal=True,
            label_visibility="collapsed",
        )
        cad_file_override: str | None = None
        if cad_mode == "Specify a file path":
            if _SOLIDWORKS_AVAILABLE:
                browse_col, _ = st.columns([1, 4])
                if browse_col.button("📂 Browse…", key="browse_cad"):
                    picked = _browse_cad_file()
                    if picked:
                        st.session_state["cad_file_path_input"] = picked
                        st.session_state.last_cad_path = picked
            cad_file_override = st.text_input(
                "Path to .SLDASM or .SLDPRT",
                value=st.session_state.get("last_cad_path", ""),
                key="cad_file_path_input",
                help="Click Browse or paste an absolute path.",
            )
            if cad_file_override:
                st.session_state.last_cad_path = cad_file_override

        st.markdown("**Mount configuration**")
        n_bot_cad, n_wall_cad = _mount_widget("cad", default_bot=6, default_wall=4)
        wall_face_cad = _wall_face_widget("cad")

        objective_cad = _objective_widget("cad")

        st.markdown("**Shock environment**")
        env_cad = _shock_env_widget("cad")

        st.markdown("**Installation clearance**")
        clr_x_cad, clr_y_cad, clr_z_cad = _clearance_widget("cad")
        cad_props_for_hint = st.session_state.get("cad_props")
        cad_mass_for_hint = (cad_props_for_hint or {}).get("mass_kg")
        if cad_mass_for_hint:
            hint_candidate_cad = _clearance_hint_candidate(
                mass_kg=cad_mass_for_hint,
                n_bottom=n_bot_cad,
                n_wall=n_wall_cad,
                env=env_cad,
                catalog=AUTO_SELECT_CATALOGS,
                objective=objective_cad,
            )
            if hint_candidate_cad:
                st.info(format_clearance_hint(hint_candidate_cad))

        if _SOLIDWORKS_AVAILABLE:
            if st.button("🔌 Extract from SolidWorks", type="primary",
                         width="stretch", key="cad_extract"):
                with st.spinner("Talking to SolidWorks via COM..."):
                    props, raw, err, rc = run_solidworks_extraction(file_path=cad_file_override)
                    st.session_state.cad_props          = props
                    st.session_state.raw_output         = raw
                    st.session_state.raw_stderr         = err
                    st.session_state.extract_returncode = rc
                    st.session_state.extract_attempted  = True
        else:
            st.button("🔌 Extract from SolidWorks", type="primary",
                      width="stretch", key="cad_extract", disabled=True)
            st.caption("Disabled on non-Windows — SolidWorks COM is unavailable here.")

    with col_right:
        props = st.session_state.cad_props
        attempted = st.session_state.get("extract_attempted", False)
        rc        = st.session_state.get("extract_returncode")
        stderr_text = st.session_state.get("raw_stderr", "")
        stdout_text = st.session_state.get("raw_output", "")

        if not props or not props.get("mass_kg"):
            if attempted:
                # Parse [CRITICAL ERROR] from stdout for a precise headline
                critical = next(
                    (line.replace("[CRITICAL ERROR]", "").strip()
                     for line in (stdout_text or "").splitlines()
                     if "[CRITICAL ERROR]" in line),
                    None,
                )
                if critical:
                    st.error(f"SolidWorks extraction failed: {critical}")
                else:
                    st.error(
                        f"Extraction returned no data (subprocess rc={rc}). "
                        "Common causes: SolidWorks not running, no active document, "
                        "or the file path you gave doesn't exist."
                    )
                if stderr_text.strip():
                    with st.expander("Subprocess stderr", expanded=True):
                        st.code(stderr_text, language="text")
                if stdout_text.strip():
                    with st.expander("Subprocess stdout (full output)", expanded=True):
                        st.text(stdout_text)
            else:
                st.info(
                    "Click **Extract from SolidWorks** to start. SolidWorks must be open "
                    "with the target assembly — OR pick **Specify a file path** above. "
                    "If SolidWorks isn't available at all, use the **Quick Selector** tab."
                )
        else:
            st.success("Extracted from SolidWorks")
            m1, m2, m3 = st.columns(3)
            m1.metric("Mass",     f"{props.get('mass_kg', 0):.1f} kg")
            m2.metric("Volume",   f"{props.get('volume_mm3', 0)/1e6:.1f} cm³")
            m3.metric("Surface",  f"{props.get('surface_mm2', 0)/1e6:.2f} m²")

            st.markdown("**Envelope (W × D × H)**")
            st.code(f"{props.get('width_mm','?')} × {props.get('depth_mm','?')} × "
                    f"{props.get('height_mm','?')} mm")

            st.markdown("**Center of Mass**")
            if props.get("cg_z_base") is not None:
                ratio = (props["cg_z_base"] / props["height_mm"] * 100) if props.get("height_mm") else 0
                st.code(
                    f"From base:    X = {props['cg_x_base']:.2f} mm\n"
                    f"              Y = {props['cg_y_base']:.2f} mm\n"
                    f"              Z = {props['cg_z_base']:.2f} mm  ({ratio:.1f}% of height)\n\n"
                    f"Raw (default origin):\n"
                    f"              X = {props.get('cg_x','?')}, Y = {props.get('cg_y','?')}, "
                    f"Z = {props.get('cg_z','?')} mm"
                )
                if ratio > 60:
                    st.warning(f"⚠ High CG: {ratio:.0f}% of height — overturn risk.")
            else:
                st.code(
                    f"X = {props.get('cg_x','?')}, Y = {props.get('cg_y','?')}, "
                    f"Z = {props.get('cg_z','?')} mm  (raw, no base-relative)"
                )

            if props.get("components"):
                with st.expander(f"BOM ({props.get('component_count')} components)"):
                    for c in props["components"]:
                        st.write(f"• {c}")

            with st.expander("Raw SolidWorks stdout"):
                st.text(st.session_state.raw_output)

    # Auto-run selection when CAD data is present
    if st.session_state.cad_props and st.session_state.cad_props.get("mass_kg"):
        st.divider()
        st.subheader("Selection Result")
        report, candidates = select_and_analyze(
            mass_kg   = st.session_state.cad_props["mass_kg"],
            n_bottom  = n_bot_cad,
            n_wall    = n_wall_cad,
            cad_props = st.session_state.cad_props,
            shock_env = env_cad,
            clr_x_mm  = clr_x_cad,
            clr_y_mm  = clr_y_cad,
            clr_z_mm  = clr_z_cad,
            objective = objective_cad,
        )
        _render_selection_result(
            report,
            candidates,
            layout_box_mm=_layout_box_from_cad_props(st.session_state.cad_props),
            clearances=(clr_x_cad, clr_y_cad, clr_z_cad),
            wall_face=wall_face_cad,
        )


# =============================================================================
# TAB — Tie-Down Provision (Appendix G / Chapter 4 of the Safety Assessment Report)
# =============================================================================
with tab_tiedown:
    st.subheader("Tie-Down Provision Check")
    st.caption("Transport restraint per MIL-STD-209K: 4G longitudinal / 2G vertical / 1.5G lateral "
               "(g=9.81). Engine validated against the MCDLL workbook — 177/177 safety factors.")

    _FACE_LABELS = {
        "Front or rear wall": MountFace.WALL_X,
        "Floor or ceiling":   MountFace.FLOOR_Z,
        "Left or right wall": MountFace.WALL_Y,
    }
    _FACE_HELP = ("Decides which axis loads the fastener in tension vs shear. "
                  "Opposing faces are equivalent (front=rear: X-normal; "
                  "floor=ceiling: Z-normal; left=right: Y-normal) -- only the "
                  "surface's normal axis matters.")
    _BOLT_CLASS_OPTS = list(BOLT_CLASSES.keys())
    _BOLT_SIZE_OPTS  = list(BOLT_SIZES.keys())
    _STRAP_OPTS      = list(NON_BOLTS.keys())

    def _td_fastener_picker(prefix: str):
        kind = st.radio("Fastener kind", ["Bolt", "Strap / Latch"], horizontal=True, key=f"{prefix}_kind")
        if kind == "Bolt":
            c1, c2 = st.columns(2)
            cls = c1.selectbox("Property class", _BOLT_CLASS_OPTS,
                               index=_BOLT_CLASS_OPTS.index("8.8"), key=f"{prefix}_cls")
            sz  = c2.selectbox("Bolt size", _BOLT_SIZE_OPTS,
                               index=_BOLT_SIZE_OPTS.index("M8"), key=f"{prefix}_sz")
            return make_fastener(cls, sz)
        name = st.selectbox("Strap / latch", _STRAP_OPTS, key=f"{prefix}_strap")
        return make_fastener(name)

    # ---- Section 1: check one item ----
    st.markdown("### 1. Check one item")
    c1, c2, c3 = st.columns([1, 1.6, 1])
    td_wt = c1.number_input("Item weight [kg]", value=60.0, min_value=0.1, max_value=5000.0,
                            step=1.0, key="td_wt")
    td_face_label = c2.selectbox("Mounting surface", list(_FACE_LABELS.keys()),
                                 key="td_face", help=_FACE_HELP)
    td_qty = c3.number_input("Fasteners (qty)", value=4, min_value=1, max_value=200, step=1, key="td_qty")
    td_fastener = _td_fastener_picker("td_chk")
    td_tgt = st.number_input("Target safety factor", value=1.0, min_value=0.1, max_value=20.0, step=0.5,
                             key="td_tgt",
                             help="Pass if the minimum SF across the 3 axes >= this. "
                                  "MIL-STD-209K design factor is 1.5.")
    if st.button("Check tie-down", type="primary", width="stretch", key="td_check_btn"):
        res = analyze_item(Item(td_fastener.name, td_wt, _FACE_LABELS[td_face_label],
                                td_fastener, int(td_qty)))
        if res.min_SF >= td_tgt:
            st.success(f"PASS — min SF = {res.min_SF:.2f} "
                       f"(limiting axis: {res.limiting_axis.axis}), target {td_tgt}")
        else:
            st.error(f"FAIL — min SF = {res.min_SF:.2f} "
                     f"(limiting axis: {res.limiting_axis.axis}) < target {td_tgt}")
        st.dataframe(
            [{"Axis": a.axis, "Design force [N]": round(a.design_force_N, 1),
              "Force type": a.force_type, "Per fastener [N]": round(a.exp_force_N, 1),
              "Yield [N]": round(a.yield_force_N, 1), "Safety factor": round(a.SF, 3)}
             for a in res.axes],
            width="stretch", hide_index=True,
        )
        st.caption(f"Fastener: **{td_fastener.name}** · tensile {td_fastener.tensile_force_N:.0f} N / "
                   f"shear {td_fastener.shear_force_N:.0f} N per fastener")

    st.divider()
    # ---- Section 2: size fasteners ----
    st.markdown("### 2. Size fasteners for a target SF")
    s1, s2, s3 = st.columns([1, 1.6, 1])
    td_swt = s1.number_input("Item weight [kg]", value=1269.0, min_value=0.1, max_value=5000.0,
                             step=1.0, key="td_swt")
    td_sface_label = s2.selectbox("Mounting surface", list(_FACE_LABELS.keys()),
                                  key="td_sface", help=_FACE_HELP)
    td_stgt = s3.number_input("Target SF", value=2.0, min_value=0.1, max_value=20.0, step=0.5, key="td_stgt")
    if st.button("Recommend fasteners", width="stretch", key="td_size_btn"):
        opts = size_fasteners(td_swt, _FACE_LABELS[td_sface_label], target_SF=td_stgt)
        best = opts[0]
        st.success(f"Smallest valid: **{best.fastener.name} x{best.qty}**  (achieved min SF {best.min_SF:.2f})")
        st.dataframe(
            [{"Fastener": o.fastener.name, "Qty": o.qty, "Achieved min SF": round(o.min_SF, 2)}
             for o in opts[:6]],
            width="stretch", hide_index=True,
        )

    st.divider()
    # ---- Section 3: generate the Appendix G report section ----
    st.markdown("### 3. Generate the Appendix G report section")
    st.caption("Runs the whole workbook, then drafts the SAR Appendix G section "
               "(scope + MIL-STD-209K basis, results table, pass/fail assessment). "
               "Every number comes from the validated engine -- no AI in the numbers.")
    rg1, rg2 = st.columns([3, 1])
    td_rg_path = rg1.text_input("Workbook path", value=WB_DEFAULT, key="td_rg_path")
    td_rg_tgt = rg2.number_input("Required SF", value=1.5, min_value=0.1, max_value=20.0,
                                 step=0.5, key="td_rg_tgt",
                                 help="MIL-STD-209K design factor is 1.5.")
    if st.button("Generate Appendix G", type="primary", width="stretch", key="td_rg_btn"):
        try:
            from tiedown_report import generate_appendix_g
            items = import_workbook(td_rg_path)
            report = run_tiedown_analysis(items, target_SF=td_rg_tgt)
            st.session_state["td_appendix_g"] = generate_appendix_g(report)
        except Exception as e:
            st.session_state["td_appendix_g"] = ""
            st.error(f"Could not generate report: {e}")
    if st.session_state.get("td_appendix_g"):
        section = st.session_state["td_appendix_g"]
        with st.expander("Preview", expanded=True):
            st.markdown(section)
        from datetime import datetime as _dt
        _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        dl1, dl2, _ = st.columns([1, 1, 3])
        dl1.download_button("Download .md", data=section, file_name=f"Appendix_G_{_ts}.md",
                            mime="text/markdown", key="td_rg_dl_md")
        dl2.download_button("Download .txt", data=section, file_name=f"Appendix_G_{_ts}.txt",
                            mime="text/plain", key="td_rg_dl_txt")

    st.divider()
    # ---- Section 5: tie-down assistant (collapsible) ----
    from tiedown_tools import TIEDOWN_CAPABILITIES
    render_domain_assistant(
        "tiedown",
        "💬 Ask the tie-down assistant",
        "e.g. 'how many M12 bolts to floor-mount a 1269 kg generator at SF 2?'",
        capabilities=TIEDOWN_CAPABILITIES,
        examples=[c["example"] for c in TIEDOWN_CAPABILITIES[:5]],
    )

    render_floating_assistant(
        "ui_guide_tiedown",
        "Tie-Down UI Guide",
        "e.g. 'which mounting surface should I pick?'",
        quickstart=[
            ("How to use tie-down", "How do I use the tie-down tab from start to finish?"),
            ("What to do first", "What should I do first to check a secured item?"),
            ("Required inputs", "What inputs do I need before running a tie-down check?"),
            ("Form or assistant", "When should I use the form controls, and when should I ask the tie-down assistant?"),
            ("Read results", "How do I read safety factor, limiting axis, force type, and PASS/FAIL?"),
        ],
    )



# =============================================================================
# TAB — Mobility and Stability Analysis (SAR Appendices B–E)
# =============================================================================
with tab_mobility:
    st.subheader("Mobility & Stability Workspace")
    st.caption(
        "This workspace helps engineers assess whether a vehicle-mounted shelter is "
        "stable before road trial. Users can load vehicle data, review the CG source, "
        "set slope and cornering conditions, then run axle load, slope stability and "
        "cornering checks against structural and OEM limits."
    )

    def _mb_set_vehicle(v, prov, approach=None, base=None, profile_key="e2"):
        """Install a newly derived vehicle; always invalidates old results.
        profile_key pins which vehicle family (analysis convention) the loaded
        vehicle belongs to, so the run step routes to the right engine."""
        st.session_state.mb_vehicle = v
        st.session_state.mb_prov = prov
        st.session_state.mb_approach = approach
        st.session_state.mb_report = None
        st.session_state.mb_base = base
        st.session_state.mb_profile_key = profile_key
        st.session_state.mb_t1_wheel_summary = None

    def _mb_clear_vehicle():
        """Failed builds/reads must never leave stale vehicle or results."""
        st.session_state.mb_vehicle = None
        st.session_state.mb_prov = None
        st.session_state.mb_approach = None
        st.session_state.mb_report = None
        st.session_state.mb_base = None
        st.session_state.mb_profile_key = None

    # ---- 0. Vehicle family ----
    # The validated engine is family-agnostic; a profile carries each family's
    # geometry, grouped axle limits, SAR angle convention and OEM margins. E2 is
    # the 2-axle Spinel; T1 is the 4-axle 8x8 reduced to two support groups.
    _MB_FAMILIES = {"Spinel E2 (2-axle)": "e2", "Spinel T1 (4-axle 8x8)": "t1"}
    mb_family_label = st.radio(
        "Vehicle family", list(_MB_FAMILIES), horizontal=True, key="mb_family",
        help="E2 = validated 2-axle baseline. T1 = 4-axle variant; axles 1+2 form "
             "the front support group and 3+4 the rear, so the same engine runs "
             "unchanged with T1's SAR angle convention and grouped vendor limits.",
    )
    mb_profile = get_profile(_MB_FAMILIES[mb_family_label])
    mb_is_t1 = mb_profile.key == "t1"

    # ---- 1. Scenario builder ----
    st.markdown("### 1. Vehicle Scenario")
    mb_mode = st.radio(
        "Vehicle source",
        ["Workbook baseline", "Wheel-load measurement", "Design / modification study",
         "Advanced: certified CG entry"],
        horizontal=True, key="mb_mode",
        help="Workbook = validated Spinel-E2 measured/theory CG (normal workflow). "
             "Wheel-load = derive CG from four weighbridge readings. "
             "Modification = add/remove/relocate components on a workbook baseline. "
             "Advanced = direct GW/CG entry with a mandatory source reference.",
    )

    if mb_mode == "Workbook baseline" and mb_is_t1:
        # T1 (.xlsx) baseline -- read via the openpyxl importer + T1 profile.
        mb_path = st.text_input(
            "T1 workbook path (.xlsx)",
            value=(t1_workbook_path() or T1_DEFAULT),
            help="T1 Measured CG workbook (sensitive -- not committed). Override via "
                 "the T1_MOBILITY_XLSX environment variable.",
            key="mb_wb_path_t1",
        )
        mb_variant = st.radio(
            "CG variant", ["measured", "theory"], horizontal=True, key="mb_variant_t1",
            help="Measured = from the T1 Measured CG sheet. "
                 "Theory = component mass-budget buildup (CAD model, no tilt test).",
        )
        if st.button("Load T1 baseline from workbook", key="mb_load_wb_t1"):
            try:
                v = (vehicle_measured_t1(mb_path) if mb_variant == "measured"
                     else vehicle_theory_t1(mb_path))
                _mb_set_vehicle(
                    v,
                    {"method": "T1 workbook baseline",
                     "source": f"{Path(mb_path).name} [{mb_variant} CG]"},
                    approach=None, profile_key="t1",
                )
            except Exception as e:
                _mb_clear_vehicle()
                st.error(f"T1 workbook read failed: {e}")
    elif mb_mode == "Workbook baseline":
        mb_path = st.text_input(
            "Workbook path (.xls)",
            value=MB_DEFAULT,
            help="Spinel-E2 Measured CG workbook. Override via MOBILITY_XLS env var.",
            key="mb_wb_path",
        )
        mb_variant = st.radio(
            "CG variant", ["measured", "theory"], horizontal=True, key="mb_variant",
            help="Measured = from physical tilt tests. Theory = from component mass budget.",
        )
        if st.button("Load baseline from workbook", key="mb_load_wb"):
            try:
                v = vehicle_measured(mb_path) if mb_variant == "measured" else vehicle_theory(mb_path)
                try:
                    mb_appr = approach_departure_angles(mb_path, mb_variant)
                except Exception:
                    mb_appr = None
                _mb_set_vehicle(
                    v,
                    {"method": "Workbook baseline",
                     "source": f"{Path(mb_path).name} [{mb_variant} CG]"},
                    mb_appr, profile_key="e2",
                )
            except Exception as e:
                _mb_clear_vehicle()
                st.error(f"Workbook read failed: {e}")
    elif mb_mode == "Wheel-load measurement" and mb_is_t1:
        # T1 four-axle (8x8) wheel-load entry -> two support groups.
        st.caption(
            "Enter the eight T1 wheel-group loads (left/right per axle). Axles 1+2 "
            "form the front support group, 3+4 the rear. Zcg is not derivable from "
            "static loads -- supply a verified value with its source."
        )
        tw_default = [3000.0, 2950.0, 3350.0, 3325.0, 3450.0, 3425.0, 3450.0, 3225.0]
        tw_vals = []
        for row_axles in ((1, 2), (3, 4)):
            cols = st.columns(4)
            for j, ax_no in enumerate(row_axles):
                li = (ax_no - 1) * 2
                tw_vals.append(cols[2 * j].number_input(
                    f"Axle {ax_no} L (kg)", value=tw_default[li], min_value=0.0,
                    step=25.0, key=f"mb_t1wl_a{ax_no}l"))
                tw_vals.append(cols[2 * j + 1].number_input(
                    f"Axle {ax_no} R (kg)", value=tw_default[li + 1], min_value=0.0,
                    step=25.0, key=f"mb_t1wl_a{ax_no}r"))
        tg1, tg2 = st.columns(2)
        tw_wb = tg1.number_input("Effective wheelbase (mm)", value=5250.0, key="mb_t1wl_wb")
        tw_tr = tg2.number_input("Track (mm)", value=2100.0, key="mb_t1wl_tr")
        tz1, tz2 = st.columns(2)
        tw_z = tz1.number_input("Zcg (mm, verified)", value=1750.4, key="mb_t1wl_z",
                                help="Above ground -- from CAD model or certified report.")
        tw_zsrc = tz2.selectbox("Zcg source", list(ZCG_SOURCES), key="mb_t1wl_zsrc")
        _gw = sum(tw_vals)
        st.caption(f"Total GW preview: {_gw:,.0f} kg "
                   f"(front group {tw_vals[0]+tw_vals[1]+tw_vals[2]+tw_vals[3]:,.0f} kg, "
                   f"rear group {tw_vals[4]+tw_vals[5]+tw_vals[6]+tw_vals[7]:,.0f} kg)")
        if st.button("Derive T1 vehicle from wheel loads", key="mb_t1wl_build"):
            try:
                summ = derive_4axle_wheel_load_summary(
                    a1_left_kg=tw_vals[0], a1_right_kg=tw_vals[1],
                    a2_left_kg=tw_vals[2], a2_right_kg=tw_vals[3],
                    a3_left_kg=tw_vals[4], a3_right_kg=tw_vals[5],
                    a4_left_kg=tw_vals[6], a4_right_kg=tw_vals[7],
                    wheelbase_mm=tw_wb, track_mm=tw_tr,
                    zcg_mm=tw_z, zcg_source=tw_zsrc,
                )
                a1, a2, a3, a4 = summ.axle_totals_kg
                _mb_set_vehicle(summ.vehicle, {
                    "method": "T1 four-axle wheel loads",
                    "source": f"axle totals {a1:.0f}/{a2:.0f}/{a3:.0f}/{a4:.0f} kg, "
                              f"Zcg from {tw_zsrc}",
                }, profile_key="t1")
                st.session_state.mb_t1_wheel_summary = summ
            except ValueError as e:
                _mb_clear_vehicle()
                st.error(f"Invalid measurement: {e}")
    elif mb_mode == "Wheel-load measurement":
        st.caption(
            "Calculate gross weight and CG from measured wheel loads.\n"
            "Use tilt-test data or a verified value for ZCG.\n"
            "Vehicle axle and GVW limits are loaded automatically."
        )
        wl1, wl2, wl3, wl4 = st.columns(4)
        wl_fl = wl1.number_input("FL (kg)", value=4000.0, min_value=0.0, step=25.0, key="mb_wl_fl")
        wl_fr = wl2.number_input("FR (kg)", value=3975.0, min_value=0.0, step=25.0, key="mb_wl_fr")
        wl_rl = wl3.number_input("RL (kg)", value=4750.0, min_value=0.0, step=25.0, key="mb_wl_rl")
        wl_rr = wl4.number_input("RR (kg)", value=5125.0, min_value=0.0, step=25.0, key="mb_wl_rr")
        wg1, wg2 = st.columns(2)
        wl_wb  = wg1.number_input("Wheelbase (mm)", value=4800.0, key="mb_wl_wb")
        wl_tr  = wg2.number_input("Track (mm)",     value=2088.0, key="mb_wl_tr")

        # Live preview of the derived values before committing
        wl_gw = wl_fl + wl_fr + wl_rl + wl_rr
        wl_f_level = wl_rl + wl_rr     # level rear-axle load (F_level)
        if wl_gw > 0:
            wl_x = wl_wb * (wl_rl + wl_rr) / wl_gw
            wl_y = wl_tr * ((wl_fr + wl_rr) / wl_gw - 0.5)
            st.caption(f"Derived preview: GW = {wl_gw:,.0f} kg | "
                       f"Xcg = {wl_x:,.1f} mm from front axle | "
                       f"Ycg = {wl_y:,.1f} mm ({'right' if wl_y >= 0 else 'left'} of centreline)")

        wl_zmethod = st.radio(
            "Zcg method", ["Derive from tilt tests", "Enter verified value"],
            horizontal=True, key="mb_wl_zmethod",
            help="Static wheel loads contain no height information. Derive Zcg "
                 "from inclined-platform tests, or enter a pre-verified value.",
        )
        wl_zcg, wl_zsrc = None, None
        if wl_zmethod == "Derive from tilt tests":
            st.caption(
                f"Zi = (Fi − F_level) × WB / (GW × tan θi) + R  with "
                f"**F_level = RL + RR = {wl_f_level:,.0f} kg**, "
                f"GW = {wl_gw:,.0f} kg, WB = {wl_wb:,.0f} mm taken from the "
                f"level readings above."
            )
            wl_rstat = st.number_input(
                "Wheel radius R (mm)", value=DEFAULT_RSTAT_MM, min_value=0.0,
                step=5.0, key="mb_wl_rstat",
                help="Static wheel radius -- tilt moments balance about the axle "
                     "centreline; R converts the result to height above ground.")
            tilt_rows = st.data_editor(
                [{"Angle (deg)": 10.2, "Inclined rear load (kg)": 10550.0},
                 {"Angle (deg)": 12.3, "Inclined rear load (kg)": 10700.0},
                 {"Angle (deg)": 8.2,  "Inclined rear load (kg)": 10450.0},
                 {"Angle (deg)": 6.2,  "Inclined rear load (kg)": 10300.0}],
                num_rows="dynamic", width="stretch", key="mb_wl_tilt",
                column_config={
                    "Angle (deg)": st.column_config.NumberColumn(
                        "Angle (deg)", min_value=0.0, max_value=89.9),
                    "Inclined rear load (kg)": st.column_config.NumberColumn(
                        "Inclined rear load (kg)", min_value=0.0),
                },
            )
            tilt_tests = [(r["Angle (deg)"], r["Inclined rear load (kg)"])
                          for r in tilt_rows
                          if r.get("Angle (deg)") and r.get("Inclined rear load (kg)")]
            if tilt_tests and wl_gw > 0:
                try:
                    tilt_results, wl_zcg = zcg_from_tilt_tests(
                        wl_f_level, wl_gw, wl_wb, tilt_tests,
                        wheel_radius_mm=wl_rstat)
                    wl_zsrc = "tilt test"
                    st.caption("  |  ".join(
                        f"Z{i} = {r.zcg_mm:,.1f} mm"
                        for i, r in enumerate(tilt_results, 1)))
                    st.success(f"Average Zcg = {wl_zcg:,.1f} mm above ground "
                               f"({len(tilt_results)} tests, source: tilt test)")
                except ValueError as e:
                    st.error(f"Invalid tilt test: {e}")
            else:
                st.info("Enter at least one tilt test (angle + inclined rear load).")
        else:
            wgz1, wgz2 = st.columns(2)
            wl_zcg = wgz1.number_input("Zcg (mm, verified)", value=1617.8, key="mb_wl_zcg",
                                       help="Above ground. From tilt test, CAD model "
                                            "or certified report -- not derivable here.")
            wl_zsrc = wgz2.selectbox("Zcg source", list(ZCG_SOURCES), key="mb_wl_zsrc")

        with st.expander("Axle / GVW limits (Spinel vendor defaults)"):
            wv1, wv2, wv3 = st.columns(3)
            wl_flim = wv1.number_input("Front axle limit (kg)",
                                       value=DEFAULT_FRONT_AXLE_LIMIT_KG, key="mb_wl_flim")
            wl_rlim = wv2.number_input("Rear axle limit (kg)",
                                       value=DEFAULT_REAR_AXLE_LIMIT_KG, key="mb_wl_rlim")
            wl_glim = wv3.number_input("GVW limit (kg)",
                                       value=DEFAULT_GVW_LIMIT_KG, key="mb_wl_glim")

        if st.button("Derive vehicle from wheel loads", key="mb_wl_build",
                     disabled=wl_zcg is None,
                     help=("Complete the tilt tests (or enter a verified Zcg) first."
                           if wl_zcg is None else None)):
            try:
                v = vehicle_from_wheel_loads(
                    wl_fl, wl_fr, wl_rl, wl_rr, wl_wb, wl_tr, wl_zcg,
                    zcg_source=wl_zsrc,
                    front_axle_limit_kg=wl_flim,
                    rear_axle_limit_kg=wl_rlim,
                    gvw_limit_kg=wl_glim,
                )
                _mb_set_vehicle(v, {
                    "method": "Wheel-load measurement",
                    "source": f"FL/FR/RL/RR = {wl_fl:.0f}/{wl_fr:.0f}/"
                              f"{wl_rl:.0f}/{wl_rr:.0f} kg, Zcg from {wl_zsrc}",
                })
            except ValueError as e:
                _mb_clear_vehicle()
                st.error(f"Invalid measurement: {e}")
    elif mb_mode == "Design / modification study":
        if mb_is_t1:
            st.info("The modification study uses the E2 baseline workbook and datum. "
                    "For T1, use **Workbook baseline** or **Wheel-load measurement** "
                    "above (T1 component-library modification is not built yet).")
        st.caption(
            "Start from a workbook baseline: browse the existing components, pick one "
            "to relocate or remove (or add new rows), then apply. Coordinates use the "
            "DESIGN datum: X rearward from the front ISO twist-lock plane, Y "
            "right-positive from the shelter centreline, Z from ground. X is converted "
            "internally to the front-axle analysis datum "
            f"(X_axle = X_ISO + {FRONT_AXLE_TO_ISO_PLANE_MM:.0f} mm)."
        )
        md1, md2 = st.columns([3, 1])
        mod_path = md1.text_input("Workbook path (.xls)", value=MB_DEFAULT,
                                  key="mb_mod_path")
        mod_variant = md2.radio("Baseline CG", ["measured", "theory"],
                                key="mb_mod_variant")

        @st.cache_data(show_spinner=False)
        def _mb_load_components(path: str):
            """Component table + shelter->vehicle datum offsets (cached per path)."""
            return shelter_components(path), shelter_datum_offsets(path)

        try:
            mod_base = (vehicle_measured(mod_path) if mod_variant == "measured"
                        else vehicle_theory(mod_path))
            mod_comps, (mod_dx, mod_dz) = _mb_load_components(mod_path)
        except Exception as e:
            st.error(f"Workbook read failed: {e}")
            mod_base, mod_comps = None, []

        # Pending-change state. The editor is keyed on mb_mod_rev so that
        # programmatic appends (Relocate/Remove buttons) can reseed it.
        ss = st.session_state
        ss.setdefault("mb_mod_pending", [])
        ss.setdefault("mb_mod_rev", 0)
        ss.setdefault("mb_mod_last", None)
        _MOD_COLS = ["Action", "Description", "Mass (kg)",
                     "Old X from front ISO (mm)",
                     "Old Y from centreline (mm, +right)",
                     "Old Z from ground (mm)",
                     "New X from front ISO (mm)",
                     "New Y from centreline (mm, +right)",
                     "New Z from ground (mm)"]
        _MOD_NUM_COLS = _MOD_COLS[2:]

        def _mb_mod_append(prefill: dict):
            """Merge the user's latest edits, then append one prefilled change row."""
            if ss.mb_mod_last is not None:
                ss.mb_mod_pending = [dict(r) for r in ss.mb_mod_last]
            row = {col: None for col in _MOD_COLS}
            row.update(prefill)
            ss.mb_mod_pending = ss.mb_mod_pending + [row]
            ss.mb_mod_rev += 1

        if mod_base is not None:
            # ---- (1) baseline summary ----
            shelter_total = sum(c.total_mass_kg for c in mod_comps)
            bsum1, bsum2, bsum3, bsum4 = st.columns(4)
            bsum1.metric("Existing components", f"{len(mod_comps)}")
            bsum2.metric("Shelter mass", f"{shelter_total:,.0f} kg")
            bsum3.metric("Baseline GW", f"{mod_base.gw_kg:,.0f} kg")
            bsum4.metric("Baseline Zcg", f"{mod_base.zcg_mm:,.1f} mm")
            st.caption(
                f"Baseline CG ({mod_variant}): Xcg = {mod_base.xcg_mm:,.1f} mm from "
                f"front axle = {axle_x_to_iso_x(mod_base.xcg_mm):,.1f} mm from front "
                f"ISO plane | Ycg = {mod_base.ycg_mm:,.1f} mm | "
                f"Zcg = {mod_base.zcg_mm:,.1f} mm above ground"
            )

            # ---- (2) read-only component browser ----
            with st.expander(f"Existing baseline components ({len(mod_comps)})",
                             expanded=False):
                fc1, fc2 = st.columns(2)
                mod_q = fc1.text_input("Search by description", key="mb_mod_search",
                                       placeholder="e.g. generator")
                mod_cats = fc2.multiselect(
                    "Filter by subsystem",
                    sorted({c.category for c in mod_comps}),
                    key="mb_mod_cats", placeholder="All subsystems")
                filtered = [
                    c for c in mod_comps
                    if (not mod_q or mod_q.lower() in c.description.lower())
                    and (not mod_cats or c.category in mod_cats)
                ]
                comp_df = pd.DataFrame([{
                    "ID": c.item_no,
                    "Subsystem": c.category,
                    "Description": c.description,
                    "Qty": c.qty,
                    "Total mass (kg)": round(c.total_mass_kg, 2),
                    "X from front ISO (mm)": round(axle_x_to_iso_x(c.x_shelter_mm + mod_dx), 1),
                    "Y (mm, +right)": round(c.y_mm, 1),
                    "Z from ground (mm)": round(c.z_shelter_mm + mod_dz, 1),
                } for c in filtered])
                ev = st.dataframe(
                    comp_df, height=320, hide_index=True, width="stretch",
                    on_select="rerun", selection_mode="single-row", key="mb_mod_list",
                )
                st.caption(
                    "Read-only baseline. Workbook shelter-frame coordinates are shown "
                    "converted to the design datum (X from front ISO plane, Z from "
                    "ground) so they match the change table 1:1."
                )

                # ---- (3) selection -> relocate / remove ----
                sel_rows = list(getattr(getattr(ev, "selection", None), "rows", []) or [])
                if sel_rows and sel_rows[0] < len(filtered):
                    sc = filtered[sel_rows[0]]
                    sc_x = round(axle_x_to_iso_x(sc.x_shelter_mm + mod_dx), 1)
                    sc_y = round(sc.y_mm, 1)
                    sc_z = round(sc.z_shelter_mm + mod_dz, 1)
                    st.markdown(
                        f"**Selected: {sc.description}** ({sc.category}, item {sc.item_no}) "
                        f"-- {sc.total_mass_kg:,.1f} kg at X={sc_x:,.1f}, Y={sc_y:,.1f}, "
                        f"Z={sc_z:,.1f} mm"
                    )
                    sb1, sb2 = st.columns(2)
                    if sb1.button("Relocate component", key="mb_mod_btn_rel",
                                  width="stretch"):
                        _mb_mod_append({
                            "Action": "relocate", "Description": sc.description,
                            "Mass (kg)": sc.total_mass_kg,
                            "Old X from front ISO (mm)": sc_x,
                            "Old Y from centreline (mm, +right)": sc_y,
                            "Old Z from ground (mm)": sc_z,
                        })
                        st.toast(f"Relocate row added for {sc.description} -- "
                                 "enter the New X/Y/Z below.")
                    if sb2.button("Remove component", key="mb_mod_btn_rem",
                                  width="stretch"):
                        _mb_mod_append({
                            "Action": "remove", "Description": sc.description,
                            "Mass (kg)": sc.total_mass_kg,
                            "Old X from front ISO (mm)": sc_x,
                            "Old Y from centreline (mm, +right)": sc_y,
                            "Old Z from ground (mm)": sc_z,
                        })
                        st.toast(f"Remove row added for {sc.description}.")
                else:
                    st.caption("Select a row above to relocate or remove that component.")

        # ---- (4) pending changes (editable; add new rows directly) ----
        st.markdown("**Proposed changes**")
        seed_df = pd.DataFrame(ss.mb_mod_pending, columns=_MOD_COLS)
        for col in _MOD_NUM_COLS:
            seed_df[col] = pd.to_numeric(seed_df[col], errors="coerce")
        mod_edit = st.data_editor(
            seed_df,
            num_rows="dynamic",
            width="stretch",
            key=f"mb_mod_table_{ss.mb_mod_rev}",
            column_config={
                "Action": st.column_config.SelectboxColumn(
                    "Action", options=["add", "remove", "relocate"], required=True),
                "Mass (kg)": st.column_config.NumberColumn("Mass (kg)", min_value=0.0),
            },
        )
        mod_rows = mod_edit.where(pd.notnull(mod_edit), None).to_dict("records")
        ss.mb_mod_last = mod_rows

        def _mod_xyz(row, prefix):
            """Read one endpoint; convert design-datum X (front ISO plane) to the
            front-axle analysis datum before it reaches apply_mass_changes()."""
            vals = (row.get(f"{prefix} X from front ISO (mm)"),
                    row.get(f"{prefix} Y from centreline (mm, +right)"),
                    row.get(f"{prefix} Z from ground (mm)"))
            if any(x is None for x in vals):
                return None
            x_iso, y, z = (float(x) for x in vals)
            return (iso_x_to_axle_x(x_iso), y, z)

        n_pending = sum(1 for r in mod_rows
                        if (r.get("Action") or "").strip() and r.get("Mass (kg)"))
        ap1, ap2 = st.columns([3, 1])
        ap1.caption(f"**{n_pending} pending change(s)** -- add uses New X/Y/Z, "
                    "remove uses Old X/Y/Z, relocate uses both (mass unchanged).")
        if ap2.button("Clear all", key="mb_mod_clear", disabled=not mod_rows):
            ss.mb_mod_pending = []
            ss.mb_mod_last = None
            ss.mb_mod_rev += 1
            st.rerun()

        if st.button("Apply changes and recalculate", key="mb_mod_build",
                     type="primary", disabled=mod_base is None):
            try:
                try:
                    mod_appr = approach_departure_angles(mod_path, mod_variant)
                except Exception:
                    mod_appr = None
                changes = []
                for i, r in enumerate(mod_rows):
                    if not (r.get("Action") or "").strip() or not r.get("Mass (kg)"):
                        continue   # skip empty / incomplete rows
                    changes.append(MassChange(
                        action=r["Action"].strip(),
                        description=(r.get("Description") or "").strip() or f"row {i + 1}",
                        mass_kg=float(r["Mass (kg)"]),
                        old_xyz_mm=_mod_xyz(r, "Old"),
                        new_xyz_mm=_mod_xyz(r, "New"),
                    ))
                v = apply_mass_changes(mod_base, changes)
                _mb_set_vehicle(
                    v,
                    {"method": "Design / modification study",
                     "source": f"{Path(mod_path).name} [{mod_variant} CG] "
                               f"+ {len(changes)} change(s)"},
                    mod_appr, base=mod_base,
                )
                if not changes:
                    st.info("No valid change rows -- modified vehicle equals the baseline.")
            except Exception as e:
                _mb_clear_vehicle()
                st.error(f"Modification failed: {e}")
    else:
        st.caption(
            "Advanced path for certified CG data only. Requires geometry, axle limits "
            "and a source/reference label. Prefer the workbook baseline for normal use."
        )
        with st.expander("Certified CG entry", expanded=False):
            ac1, ac2, ac3, ac4 = st.columns(4)
            adv_gw  = ac1.number_input("GW (kg)",  value=17850.0, key="mb_adv_gw")
            adv_xcg = ac2.number_input("Xcg (mm)", value=2655.5,  key="mb_adv_xcg",
                                       help="From front axle, positive rearward")
            adv_ycg = ac3.number_input("Ycg (mm)", value=20.5,    key="mb_adv_ycg",
                                       help="From centreline, right-positive")
            adv_zcg = ac4.number_input("Zcg (mm)", value=1617.8,  key="mb_adv_zcg",
                                       help="Above ground")
            ag1, ag2, ag3, ag4, ag5 = st.columns(5)
            adv_wb  = ag1.number_input("Wheelbase (mm)", value=4800.0, key="mb_adv_wb")
            adv_tr  = ag2.number_input("Track (mm)",     value=2088.0, key="mb_adv_tr")
            adv_fl  = ag3.number_input("Front axle limit (kg)",
                                       value=DEFAULT_FRONT_AXLE_LIMIT_KG, key="mb_adv_flim")
            adv_rl  = ag4.number_input("Rear axle limit (kg)",
                                       value=DEFAULT_REAR_AXLE_LIMIT_KG, key="mb_adv_rlim")
            adv_gvw = ag5.number_input("GVW limit (kg)",
                                       value=DEFAULT_GVW_LIMIT_KG, key="mb_adv_glim")
            adv_src = st.text_input(
                "CG source / reference (required)", key="mb_adv_src",
                placeholder="e.g. OEM homologation cert 123-A, tilt test report TR-07",
            )
            if st.button("Build vehicle from certified CG", key="mb_adv_build"):
                try:
                    v = vehicle_from_certified_cg(
                        adv_gw, adv_xcg, adv_ycg, adv_zcg, adv_wb, adv_tr,
                        source=adv_src,
                        front_axle_limit_kg=adv_fl,
                        rear_axle_limit_kg=adv_rl,
                        gvw_limit_kg=adv_gvw,
                    )
                    _mb_set_vehicle(v, {"method": "Certified CG entry",
                                        "source": adv_src.strip()},
                                    profile_key=mb_profile.key)
                except ValueError as e:
                    _mb_clear_vehicle()
                    st.error(f"Invalid scenario: {e}")

    st.divider()

    # ---- 2. Derived vehicle summary + provenance ----
    st.markdown("### 2. Derived Vehicle & Provenance")
    mb_v = st.session_state.mb_vehicle
    if mb_v is None:
        st.info("No vehicle loaded yet -- build a scenario in step 1.")
    else:
        mb_prov = st.session_state.mb_prov or {}
        st.caption(
            f"Source: **{mb_prov.get('method', '?')}** -- {mb_prov.get('source', '?')}  |  "
            f"Datum: X from front axle, Y right-positive from centreline, Z from ground"
        )
        mb_base = st.session_state.mb_base
        d = baseline_delta(mb_base, mb_v) if mb_base is not None else None
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("GW",   f"{mb_v.gw_kg:,.0f} kg",
                  delta=f"{d['gw_kg']:+,.0f} kg" if d else None, delta_color="off")
        s2.metric("Xcg",  f"{mb_v.xcg_mm:,.1f} mm",
                  delta=f"{d['xcg_mm']:+,.1f} mm" if d else None, delta_color="off")
        s3.metric("Ycg",  f"{mb_v.ycg_mm:,.1f} mm",
                  delta=f"{d['ycg_mm']:+,.1f} mm" if d else None, delta_color="off")
        s4.metric("Zcg",  f"{mb_v.zcg_mm:,.1f} mm",
                  delta=f"{d['zcg_mm']:+,.1f} mm" if d else None, delta_color="off")
        s5.metric("Wheelbase", f"{mb_v.wheelbase_mm:,.0f} mm")
        s6.metric("Track",     f"{mb_v.track_mm:,.0f} mm")
        if d is not None:
            st.caption(f"Deltas vs baseline: {mb_base.name} "
                       f"(GW {mb_base.gw_kg:,.0f} kg, Xcg {mb_base.xcg_mm:,.1f}, "
                       f"Ycg {mb_base.ycg_mm:,.1f}, Zcg {mb_base.zcg_mm:,.1f} mm)")

        # Dual-datum CG readout: physics runs on the front-axle datum; engineers
        # design against the front ISO twist-lock plane. The plane offset is
        # family-specific (E2 1450 mm, T1 2400 mm) -- use the loaded vehicle's
        # profile so the design-datum X is correct per variant.
        _iso_off = (get_profile(st.session_state.mb_profile_key).iso_plane_offset_mm
                    if st.session_state.get("mb_profile_key")
                    else FRONT_AXLE_TO_ISO_PLANE_MM)
        xcg_iso = mb_v.xcg_mm - _iso_off
        y_side = "right of" if mb_v.ycg_mm >= 0 else "left of"
        st.markdown(
            f"**Analysis datum: Front axle** — XCG = {mb_v.xcg_mm:,.1f} mm  \n"
            f"**Design datum: Front ISO twist-lock plane** — XCG = {xcg_iso:,.1f} mm  \n"
            f"YCG = {abs(mb_v.ycg_mm):,.1f} mm {y_side} centreline  •  "
            f"ZCG = {mb_v.zcg_mm:,.1f} mm above ground"
        )
        with st.expander("CG datum label (design datum O)"):
            st.code(
                "Datum O:\n"
                "X = front ISO twist-lock plane\n"
                "Y = shelter centreline\n"
                "Z = ground level\n"
                "\n"
                "+X rearward\n"
                "+Y right\n"
                "+Z upward\n"
                "\n"
                f"Combined CG: ({xcg_iso:,.1f}, {mb_v.ycg_mm:,.1f}, "
                f"{mb_v.zcg_mm:,.1f}) mm",
                language=None,
            )
        for w in check_cg_plausibility(mb_v):
            st.warning(w)

        if st.session_state.get("mb_profile_key") == "t1":
            st.markdown("#### T1 axle grouping")
            st.code(
                format_profile_axle_context(
                    T1_PROFILE,
                    wheel_summary=st.session_state.get("mb_t1_wheel_summary")),
                language="text",
            )
            st.caption("The 4-axle vehicle is reduced to two support lines; the "
                       "validated engine treats each group as one 'axle', so the "
                       "front-group / rear-group loads below map onto axles 1+2 / 3+4.")

        from vehicle_cg_viz import side_view_figure, rear_view_figure

        _cg_base = mb_base if mb_base is not None else mb_v
        _cg_mod = mb_v if mb_base is not None else None
        with st.expander("CG position and tip geometry", expanded=True):
            st.caption(
                "Deterministic side and rear views from the derived vehicle. The "
                "CG dot is the computed centre of gravity; each dashed line is a "
                "tip-over pivot and its angle is the engine's critical tip angle. "
                "Blue is the baseline"
                + (", coral is after the change." if _cg_mod is not None else ".")
            )
            _side = side_view_figure(_cg_base, modified=_cg_mod)
            _rear = rear_view_figure(_cg_base, modified=_cg_mod)
            _side.update_layout(height=440)
            _rear.update_layout(height=440)
            _gc1, _gc2 = st.columns(2)
            _gc1.plotly_chart(_side, config={"displaylogo": False})
            _gc2.plotly_chart(_rear, config={"displaylogo": False})

    st.divider()

    # ---- 3. Analysis assumptions ----
    st.markdown("### 3. Analysis Assumptions")
    aa1, aa2 = st.columns(2)
    mb_grades_long = aa1.multiselect(
        "Longitudinal slope grades (%)", [70, 60, 50, 40, 30, 20], default=[60, 50],
        key="mb_grades_long",
        help="Each selected grade is tested in BOTH ascending and descending directions.")
    mb_grades_side = aa2.multiselect(
        "Side-slope grades (%)", [40, 30, 25, 20, 15], default=[30, 25],
        key="mb_grades_side",
        help="Each selected grade is tested leaning toward BOTH kerbside and roadside.")

    # Make the generated directional cases explicit (mirror the engine's empty-input
    # fallback at the run_mobility_analysis call below so the preview never lies).
    _long = list(mb_grades_long) or [60, 50]
    _side = list(mb_grades_side) or [30, 25]
    _ang = lambda g: math.degrees(math.atan(g / 100))          # 60% -> 31.0°
    st.caption(f"**Tests that will run: {2 * len(_long) + 2 * len(_side)}**")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**Longitudinal** — ascending + descending")
        for g in sorted(_long, reverse=True):
            st.markdown(f"- Ascending {g}% ({_ang(g):.1f}°)  •  Descending {g}% ({_ang(g):.1f}°)")
    with pc2:
        st.markdown("**Side-slope** — kerbside + roadside")
        for g in sorted(_side, reverse=True):
            st.markdown(f"- Kerbside {g}% ({_ang(g):.1f}°)  •  Roadside {g}% ({_ang(g):.1f}°)")

    # Per-family widget keys: switching family loads that family's defaults
    # (E2 radius 11 m / margins 2.0-2.2; T1 radius 14 m / margins 1.5).
    ab1, ab2, ab3 = st.columns(3)
    mb_speed = ab1.slider("Cornering speed (km/h)", 5, 60, 15, key="mb_speed")
    mb_radius = ab2.slider("Turning radius (m)", 5, 50,
                           int(round(mb_profile.default_radius_m)),
                           key=f"mb_radius_{mb_profile.key}",
                           help="Minimum turning radius. Default is the "
                                f"{mb_profile.display_name} value "
                                f"({mb_profile.default_radius_m:.0f} m).")
    mb_wind = ab3.slider("Wind (km/h)", 0, 100, 60, key="mb_wind")
    with st.expander("OEM recommended margins (verdict thresholds)"):
        st.caption(f"Defaults shown are the {mb_profile.display_name} SAR-stated "
                   "recommended safety factors.")
        om1, om2, om3 = st.columns(3)
        mb_m_long = om1.number_input("Longitudinal", value=mb_profile.oem_margin_long,
                                     min_value=1.0, step=0.1,
                                     key=f"mb_m_long_{mb_profile.key}",
                                     help="Applied to EVERY selected longitudinal grade "
                                          "(ascending and descending).")
        mb_m_lat = om2.number_input("Lateral", value=mb_profile.oem_margin_lat,
                                    min_value=1.0, step=0.1,
                                    key=f"mb_m_lat_{mb_profile.key}",
                                    help="Applied to EVERY selected side-slope grade "
                                         "(kerbside and roadside).")
        mb_m_corner = om3.number_input("Cornering", value=mb_profile.oem_margin_corner,
                                       min_value=1.0, step=0.1,
                                       key=f"mb_m_corner_{mb_profile.key}")

    st.divider()

    # ---- 4. Unified results ----
    st.markdown("### 4. Full Mobility Analysis")
    if st.button("Run Analysis", key="mb_run", type="primary",
                 disabled=(mb_v is None),
                 help=None if mb_v is not None else "Build a scenario in step 1 first"):
        try:
            _long = tuple(mb_grades_long) or (60, 50)
            _side = tuple(mb_grades_side) or (30, 25)
            if st.session_state.get("mb_profile_key") == "t1":
                # T1: apply the SAR angle/trig convention + T1 aero via the
                # profile runner, so the SFs match the workbook exactly.
                report = run_profile_mobility_analysis(
                    mb_v, T1_PROFILE,
                    grades_long=_long, grades_side=_side,
                    speed_kmh=float(mb_speed),
                    radius_m=float(mb_radius),
                    wind_kmh=float(mb_wind),
                )
            else:
                mb_appr = st.session_state.mb_approach
                report = run_mobility_analysis(
                    mb_v,
                    grades_long=_long,
                    grades_side=_side,
                    speed_kmh=float(mb_speed),
                    radius_m=float(mb_radius),
                    wind_kmh=float(mb_wind),
                    approach_deg=mb_appr[0] if mb_appr else None,
                    departure_deg=mb_appr[1] if mb_appr else None,
                )
            st.session_state.mb_report = report
        except Exception as e:
            st.session_state.mb_report = None
            st.error(f"Analysis failed: {e}")

    mb_rep = st.session_state.mb_report
    if mb_rep is not None:
        # Verdicts (3-tier vs OEM margins)
        slope_verdicts = [
            sf_verdict(r.SF, margin_for_direction(r.direction, mb_m_long, mb_m_lat))
            for r in mb_rep.slope_results
        ]
        corner_verdict = (sf_verdict(mb_rep.corner.SF, mb_m_corner)
                          if mb_rep.corner else None)
        all_verdicts = slope_verdicts + ([corner_verdict] if corner_verdict else [])
        # Compliance precedence, worst first: a structural failure (axle / GVW /
        # steerability) outranks every stability verdict (engine: AxleResult.all_ok).
        ax = mb_rep.axle
        if not ax.all_ok:
            overall = VERDICT_STRUCTURAL
            failed = [name for name, ok in [
                ("front axle", ax.front_ok), ("rear axle", ax.rear_ok),
                ("GVW", ax.gvw_ok), ("steerability (front < 25% GW)", ax.steer_ok),
            ] if not ok]
            st.error(f"Structural limit exceeded: {', '.join(failed)}. "
                     "See the axle table below — stability SFs alone do not make "
                     "this configuration compliant.")
        elif VERDICT_UNSTABLE in all_verdicts:
            overall = VERDICT_UNSTABLE
        elif VERDICT_BELOW in all_verdicts:
            overall = VERDICT_BELOW
        else:
            overall = VERDICT_MEETS

        gov = mb_rep.governing_slope()
        h1, h2, h3 = st.columns(3)
        h1.metric("Governing slope SF", f"{gov.SF:.4f}" if gov else "--",
                  f"{gov.direction} {gov.grade_pct:.0f}%" if gov else "")
        h2.metric("Cornering SF",
                  f"{mb_rep.corner.SF:.3f}" if mb_rep.corner else "--",
                  f"max safe {mb_rep.corner.max_safe_speed_kmh:.1f} km/h"
                  if mb_rep.corner else "")
        h3.metric("Overall verdict", overall)

        # Axle loads, structural limits and margins. For T1 the two engine
        # "axles" are really the front/rear support GROUPS (axles 1+2 / 3+4).
        _rep_is_t1 = st.session_state.get("mb_profile_key") == "t1"
        _front_lbl = "Front group (axles 1+2)" if _rep_is_t1 else "Front axle"
        _rear_lbl = "Rear group (axles 3+4)" if _rep_is_t1 else "Rear axle"
        st.markdown("**Axle loads vs structural / OEM limits**")
        st.dataframe(
            [
                {"Check": _front_lbl, "Load": round(ax.front_kg, 1),
                 "Limit": mb_v.front_axle_limit_kg,
                 "Margin": round(mb_v.front_axle_limit_kg - ax.front_kg, 1),
                 "Unit": "kg",
                 "Status": "[OK]" if ax.front_ok else "[OVER LIMIT]"},
                {"Check": _rear_lbl, "Load": round(ax.rear_kg, 1),
                 "Limit": mb_v.rear_axle_limit_kg,
                 "Margin": round(mb_v.rear_axle_limit_kg - ax.rear_kg, 1),
                 "Unit": "kg",
                 "Status": "[OK]" if ax.rear_ok else "[OVER LIMIT]"},
                {"Check": "GVW", "Load": round(mb_v.gw_kg, 1),
                 "Limit": mb_v.gvw_limit_kg,
                 "Margin": round(mb_v.gvw_limit_kg - mb_v.gw_kg, 1),
                 "Unit": "kg",
                 "Status": "[OK]" if ax.gvw_ok else "[OVER LIMIT]"},
                {"Check": "Steerability (front >= 25% GW)",
                 "Load": round(ax.front_pct, 1), "Limit": 25.0,
                 "Margin": round(ax.front_pct - 25.0, 1),
                 "Unit": "%",
                 "Status": "[OK]" if ax.steer_ok else "[FAIL]"},
            ],
            hide_index=True, width="stretch",
        )

        # Slope SF table with 3-tier verdicts
        st.markdown("**Slope stability**")
        st.dataframe(
            [
                {"Grade (%)": r.grade_pct, "Direction": r.direction,
                 "SF": round(r.SF, 4),
                 "Crit. tip angle (deg)": round(r.crit_angle_deg, 1),
                 "OEM margin": margin_for_direction(r.direction, mb_m_long, mb_m_lat),
                 "Verdict": vd}
                for r, vd in zip(mb_rep.slope_results, slope_verdicts)
            ],
            hide_index=True, width="stretch",
        )
        if gov:
            st.info(f"Governing case: {gov.direction} {gov.grade_pct:.0f}% -- "
                    f"SF = {gov.SF:.4f}, critical tip angle = {gov.crit_angle_deg:.1f} deg")

        # Cornering
        if mb_rep.corner:
            c = mb_rep.corner
            st.markdown(
                f"**Cornering** @{c.speed_kmh:.0f} km/h, R={c.radius_m:.0f} m, "
                f"wind {c.wind_kmh:.0f} km/h: SF = **{c.SF:.3f}** "
                f"({corner_verdict}) | max safe speed = **{c.max_safe_speed_kmh:.1f} km/h**"
            )
            st.caption(
                f"Overturning: Fc x Zcg = {c.over_fc_Nm:,.0f} Nm + "
                f"Fw x h = {c.over_wind_Nm:,.0f} Nm = {c.over_total_Nm:,.0f} Nm  |  "
                f"Resist = {c.resist_Nm:,.0f} Nm  (Y' = {c.yprime_mm:.0f} mm)"
            )

    st.divider()

    # ---- 4b. ISO twist-lock strength (T1 only) ----
    if st.session_state.get("mb_profile_key") == "t1":
        st.markdown("### 4b. ISO Twist-Lock Strength Check")
        st.caption(
            "Per-lock retention forces on the four ISO corner twist-locks under the "
            "T1 design accelerations (4.0g longitudinal / 1.5g lateral / 2.0g "
            "vertical). Uses the shelter/payload weight carried on the locks, not "
            "the full GVW. Allowables: 170 / 170 / 85 kN per lock."
        )
        tl1, tl2 = st.columns([2, 1])
        if st.session_state.get("mb_tl_weight_default") is None:
            try:
                st.session_state.mb_tl_weight_default = float(
                    payload_cg_from_measured_t1().mass_kg)
            except Exception:
                st.session_state.mb_tl_weight_default = 9725.0
        tl_weight = tl1.number_input(
            "Shelter / payload weight (kg)",
            value=st.session_state.mb_tl_weight_default, min_value=0.0, step=50.0,
            key="mb_tl_weight",
            help="Weight retained by the ISO locks. Default = reverse-CG payload "
                 "from the T1 measured workbook (~9725 kg).")
        tl_n = tl2.number_input("Number of locks", value=4, min_value=1, step=1,
                                key="mb_tl_n")
        if st.button("Check twist-lock strength", key="mb_tl_run"):
            try:
                st.session_state.mb_tl_report = analyze_twist_locks(
                    float(tl_weight), n_locks=int(tl_n))
            except Exception as e:
                st.session_state.mb_tl_report = None
                st.error(f"Twist-lock check failed: {e}")
        tl_rep = st.session_state.get("mb_tl_report")
        if tl_rep is not None:
            tlc = st.columns(3)
            for col, a in zip(tlc, tl_rep.axes):
                col.metric(f"{a.axis.title()} SF", f"{a.SF:.2f}",
                           f"{a.force_per_lock_N / 1000:.1f} kN/lock",
                           delta_color="off")
            st.dataframe([
                {"Axis": a.axis, "Design g": a.load_factor,
                 "Design force (kN)": round(a.design_force_N / 1000, 1),
                 "Per lock (kN)": round(a.force_per_lock_N / 1000, 1),
                 "Allowable (kN)": round(a.allowable_N / 1000, 1),
                 "SF": round(a.SF, 2),
                 "Status": "[OK]" if a.passed else "[FAIL]"}
                for a in tl_rep.axes
            ], hide_index=True, width="stretch")
            if tl_rep.all_passed:
                st.success(f"All {tl_rep.n_locks} twist-locks pass "
                           f"(min SF = {tl_rep.min_SF:.2f}).")
            else:
                st.error(f"Twist-lock check FAILED (min SF = {tl_rep.min_SF:.2f}) -- "
                         "per-lock force exceeds allowable on at least one axis.")
        st.divider()

    # ---- 5. Generate SAR Appendices B-E (.docx) ----
    st.markdown("### 5. Generate SAR Appendices B–E (Word .docx)")
    if mb_is_t1:
        st.info("The Word SAR appendix generator currently targets the **E2** variant "
                "(Appendix B needs the E2 wheel-load + tilt-test workbook). T1 safety "
                "factors are validated above against the T1 workbook; the T1 Word "
                "report is planned future work.")
    # SAR always derives from the measured workbook (Appendix B needs raw wheel
    # loads + tilt tests). Falls back to defaults if workbook mode not active.
    mb_sar_path = st.session_state.get("mb_wb_path", MB_DEFAULT) or MB_DEFAULT
    mb_sar_variant = st.session_state.get("mb_variant", "measured")
    st.caption("Drop-in replica of the SAR mobility appendices. Reproduces the published "
               "safety factors (2.21 / 2.73 / 2.20 / 2.11 / 3.12). Figures inserted as placeholders.")
    mb4_project  = st.text_input("Project", value="Project Spinel", key="mb4_proj")
    mb4_variant_lbl = st.text_input("Variant", value="Variant E-2", key="mb4_var")

    if st.button("Generate Appendices B–E (.docx)", key="mb4_gen", disabled=mb_is_t1,
                 help=("Word SAR generation currently supports E2 only; T1 is future work."
                       if mb_is_t1 else None)):
        try:
            if mb_sar_variant != "measured":
                st.warning("Appendix B (wheel-load derivation) uses Measured-CG data. "
                           "Switch CG variant to 'measured' for the full B-E set.")
            v4 = vehicle_measured(mb_sar_path)
            m4 = measurement_measured(mb_sar_path)
            mu4 = measurement_unladen(mb_sar_path)
            sh4 = shelter_cg(mb_sar_path)
            from sar_report import generate_sar_appendices
            from io import BytesIO
            doc = generate_sar_appendices(
                v4, m4, m_unladen=mu4, shelter=sh4,
                project=mb4_project, variant=mb4_variant_lbl,
            )
            buf = BytesIO()
            doc.save(buf)
            buf.seek(0)

            # quick on-screen confirmation of the headline SFs
            from mobility_engine import slope_stability, side_slope_stability, cornering_stability
            sf_a = slope_stability(v4, 60, "ascending", angle_deg=31.0, trig_dp=3).SF
            sf_d = slope_stability(v4, 60, "descending", angle_deg=31.0, trig_dp=3).SF
            sf_k = side_slope_stability(v4, 30, "kerbside", angle_deg=16.7, trig_dp=3).SF
            sf_r = side_slope_stability(v4, 30, "roadside", angle_deg=16.7, trig_dp=3).SF
            sf_c = cornering_stability(v4, Aero(), 15, 11, 60).SF
            st.success("Generated appendices B (B.1+B.2+B.3), C, D, E.")
            if abs(sh4.ycg_mm - 152.2) > 1:
                st.warning(f"Note: workbook computes Laden E2 Shelter Ycg = {sh4.ycg_mm:.1f} mm, "
                           f"but the signed SAR Table B-4 shows 152.2 mm — likely a digit "
                           f"transposition (125.2 → 152.2) in the report. Output uses the "
                           f"workbook-computed value.")
            mcols = st.columns(5)
            for col, (lbl, val) in zip(mcols, [
                ("C.1 Asc 60%", sf_a), ("C.2 Desc 60%", sf_d),
                ("D.1 Kerb 30%", sf_k), ("D.2 Road 30%", sf_r), ("E Corner", sf_c)]):
                col.metric(lbl, f"{val:.2f}")

            import datetime
            _ts4 = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                "⬇ Download Appendices B–E (.docx)",
                data=buf,
                file_name=f"Appendix_BCDE_{_ts4}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="mb4_dl_docx",
            )
        except Exception as e:
            st.error(f"Error generating appendices: {e}")

    st.divider()

    # ---- 6. Mobility assistant (collapsible) ----
    from mobility_tools import MOBILITY_CAPABILITIES
    render_domain_assistant(
        "mobility",
        "💬 Ask the mobility assistant",
        "e.g. 'is the Spinel E2 stable on a 60% slope?'",
        capabilities=MOBILITY_CAPABILITIES,
        examples=[c["example"] for c in MOBILITY_CAPABILITIES[:5]],
    )

    render_floating_assistant(
        "ui_guide_mobility",
        "Mobility UI Guide",
        "e.g. 'why is Run Analysis disabled?'",
        quickstart=[
            ("How to use mobility", "How do I use the mobility tab from start to finish?"),
            ("What to do first", "What should I do first to analyse the vehicle?"),
            ("Required inputs", "What inputs do I need before running mobility analysis?"),
            ("Form or assistant", "When should I use the workbook/forms, and when should I ask the mobility assistant?"),
            ("Read results", "How do I read axle load, slope stability, cornering, and final verdicts?"),
        ],
    )



# ----------------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------------

st.divider()
st.caption(
    "Physics: 4 load cases per `Shock Isolator_850kg_4 Bayed 35U.xls` reference  ·  "
    "Catalog: Helical CB61400 / CB1400 / CB1500 / CB1700  ·  "
    "Agent: NVIDIA Llama 3.1 70B (tool calling)"
)
