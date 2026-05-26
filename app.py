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
import subprocess
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st

from cad_compliance_checker import _parse_cad_output
from physics_engine import ShockEnv, _loads_per_isolator, run_analysis
from catalog import (
    ALL_CATALOGS, AUTO_SELECT_CATALOGS,
    CB61400_CATALOG, CB1400_CATALOG, CB1500_CATALOG, CB1700_CATALOG,
    select_isolator, select_and_analyze, format_selection_table, format_report,
)


# ----------------------------------------------------------------------------
# Page config + environment
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="CAD Agent — Shock Mount",
    page_icon="🔧",
    layout="wide",
)

load_dotenv()
API_KEY = (os.environ.get("NVIDIA_API_KEY") or "").strip()

SERIES_MAP = {
    "All series (CB1400 + CB1500 + CB1700)":            AUTO_SELECT_CATALOGS,
    "CB1400 (1/2\" wire)":                              CB1400_CATALOG,
    "CB1500 (5/8\" wire)":                              CB1500_CATALOG,
    "CB1700 (7/8\" wire)":                              CB1700_CATALOG,
    "All incl. CB61400 (6-strand softer, opt-in)":      ALL_CATALOGS,
    "CB61400 only (6-strand 1/2\" wire)":               CB61400_CATALOG,
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
    """Render a 3-column shock environment input row; return a ShockEnv."""
    c1, c2, c3 = st.columns(3)
    Ao = c1.number_input("Shock Ao [G]",       value=20.0, min_value=1.0,  max_value=60.0,
                         step=1.0, key=f"{prefix}_Ao")
    to = c2.number_input("Pulse to [ms]",      value=11.0, min_value=1.0,  max_value=100.0,
                         step=1.0, key=f"{prefix}_to")
    GL = c3.number_input("GT limit [G]",       value=10.0, min_value=1.0,  max_value=50.0,
                         step=1.0, key=f"{prefix}_GL")
    return ShockEnv(Ao_G=Ao, to_s=to / 1000.0, GT_limit_G=GL)


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


def _render_selection_result(report, candidates):
    """Render the selection result section: recommended part, then per-case table."""
    valid = [c for c in candidates if c.valid]
    rec   = valid[0] if valid else None

    if rec:
        st.success(f"**Recommended: {rec.entry.part_no}** "
                   f"(Series {rec.entry.series}, "
                   f"worst GT = {rec.worst_GT_ratio*100:.0f}% of limit)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("K_comp",  f"{rec.entry.k_comp_lbin} lb/in")
        m2.metric("K_shear", f"{rec.entry.k_shear_lbin} lb/in")
        m3.metric("Size",    f"H={rec.entry.H_in}\" W={rec.entry.W_in}\"")
        m4.metric("Worst dD ratio", f"{rec.worst_delta_ratio*100:.0f}%")
    else:
        st.error("No valid part found in the selected catalog. Try more mounts, "
                 "a larger series, or a looser GT limit.")

    # 4-case table for the recommended part
    if rec:
        st.subheader("4 Load Cases (all must pass)")
        rows = []
        for d in [rec.comp_bottom, rec.comp_wall, rec.roll_wall, rec.roll_bottom]:
            rows.append({
                "Case":          d.label,
                "m [kg]":        round(d.m_kg, 2),
                "fn [Hz]":       round(d.fn_Hz, 3),
                "GT [G]":        round(d.GT_G, 3),
                "GT limit":      d.GT_limit,
                "dD [mm]":       round(d.delta_mm, 2),
                "dD limit [mm]": round(d.delta_limit_mm, 2),
                "PASS":          "✅" if d.passed else "❌",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # Full catalog comparison
    with st.expander("📊 Full multi-series matrix"):
        st.code(format_selection_table(candidates), language="text")

    # Physics report
    with st.expander("🔬 Full physics report"):
        st.code(format_report(report), language="text")


# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.title("🔧 CAD Agent — Shock Mount Selection")
st.caption("Wire rope isolator selection for chassis-mounted shelter equipment · FYP 2026")

if not API_KEY:
    st.warning(
        "⚠ `NVIDIA_API_KEY` not set in your environment / `.env` file. "
        "The **Quick Selector** and **CAD + Shock** tabs work without it, "
        "but the **Agent Chat** tab requires it."
    )


# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_quick, tab_cad, tab_agent = st.tabs([
    "📐 Quick Selector",
    "🔌 CAD + Shock",
    "🤖 Agent Chat",
])


# =============================================================================
# TAB 1 — Quick Selector (manual entry, server-friendly, no SolidWorks needed)
# =============================================================================
with tab_quick:
    st.subheader("Isolator Selector")
    st.caption("Enter the assembly mass directly. Useful when SolidWorks isn't running "
               "or you're working from spec sheets.")

    sel_mode = st.radio(
        "Mode",
        ["Auto (recommend best part)", "Manual (verify a specific part)"],
        horizontal=True,
        key="q_sel_mode",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        mass_kg = st.number_input("Total assembly mass [kg]", value=850.0,
                                  min_value=1.0, max_value=10000.0, step=10.0, key="q_mass")
    with c2:
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

    st.markdown("**Mount configuration**")
    n_bot, n_wall = _mount_widget("q", default_bot=6, default_wall=4)

    st.markdown("**Shock environment**")
    env = _shock_env_widget("q")

    btn_label = "🎯 Select Best Isolator" if sel_mode == "Auto (recommend best part)" else "📊 Run Analysis"
    if st.button(btn_label, type="primary", use_container_width=True, key="q_run"):
        if sel_mode == "Auto (recommend best part)":
            with st.spinner("Running 4-case selection..."):
                report, candidates = select_and_analyze(
                    mass_kg   = mass_kg,
                    n_bottom  = n_bot,
                    n_wall    = n_wall,
                    cad_props = None,
                    shock_env = env,
                    catalog   = SERIES_MAP[series_label],
                )
        else:
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
                )
                report = run_analysis(
                    mass_kg, n_bot, n_wall,
                    shock_env = env,
                    isolator  = entry.to_isolator_spec(),
                )
        _render_selection_result(report, candidates)


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
        cad_mode = st.radio(
            "Where to extract from:",
            ["Use active SolidWorks document", "Specify a file path"],
            key="cad_source_mode",
            horizontal=True,
            label_visibility="collapsed",
        )
        cad_file_override: str | None = None
        if cad_mode == "Specify a file path":
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

        st.markdown("**Shock environment**")
        env_cad = _shock_env_widget("cad")

        if st.button("🔌 Extract from SolidWorks", type="primary",
                     use_container_width=True, key="cad_extract"):
            with st.spinner("Talking to SolidWorks via COM..."):
                props, raw, err, rc = run_solidworks_extraction(file_path=cad_file_override)
                st.session_state.cad_props          = props
                st.session_state.raw_output         = raw
                st.session_state.raw_stderr         = err
                st.session_state.extract_returncode = rc
                st.session_state.extract_attempted  = True

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
        )
        _render_selection_result(report, candidates)


# =============================================================================
# TAB 3 — Agent Chat (LLM with tool calling)
# =============================================================================
with tab_agent:
    st.subheader("Engineering Assistant")
    st.caption("LLM-driven agent with 5 tools: extract CAD, select isolator, run shock analysis, "
               "lookup knowledge base, list CAD files.")

    if not API_KEY:
        st.error("Agent chat requires `NVIDIA_API_KEY` in `.env`. "
                 "The selector tabs above don't need it.")
    else:
        # Cache the agent object at the process level so the NVIDIA endpoint
        # handshake and LangChain tool registration only happen once, regardless
        # of how many Streamlit reruns occur. Each stream() call is still a fresh
        # LLM request — only the constructor is cached, not any answers.
        # Caveat: if API_KEY changes or agent.py is edited, restart the app.
        @st.cache_resource
        def _get_agent(key: str):
            from agent import ShockMountAgent
            return ShockMountAgent(key)

        if st.session_state.agent is None:
            with st.spinner("Initializing agent (Llama 3.1 70B + 5 tools)..."):
                try:
                    st.session_state.agent = _get_agent(API_KEY)
                except Exception as e:
                    st.error(f"Failed to initialize agent: {e}")

        # ----- helper: render the tool-call trace for one assistant turn -----
        def _render_trace(events: list[dict]):
            """Render a list of streaming events from the agent inside an expander."""
            if not events:
                return
            with st.expander(f"🔎 Show {len(events)} agent steps", expanded=False):
                for i, ev in enumerate(events, 1):
                    if ev["type"] == "reasoning":
                        st.markdown(f"**{i}. 💭 Reasoning**")
                        st.markdown(f"> {ev['content']}")
                    elif ev["type"] == "tool_call":
                        args_lines = [f"  {k} = {v!r}" for k, v in ev["args"].items()]
                        st.markdown(f"**{i}. 🔧 Calling `{ev['name']}`**")
                        st.code("\n".join(args_lines) or "(no args)", language="python")
                    elif ev["type"] == "tool_result":
                        preview = ev["content"]
                        if len(preview) > 800:
                            preview = preview[:800] + f"\n... ({len(ev['content'])-800} more chars)"
                        st.markdown(f"**{i}. ✅ Result from `{ev['name']}`**")
                        st.code(preview, language="text")

        # ----- render conversation history (including past tool traces) -----
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                if msg.get("events"):
                    _render_trace(msg["events"])
                st.markdown(msg["content"])

        # ----- new user input -----
        user_q = st.chat_input("Ask anything (e.g. 'what isolator for 1200kg, 6+4 mounts?')")
        if user_q and st.session_state.agent is not None:
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            # Build LangChain-style chat history from prior turns
            hist = []
            for m in st.session_state.chat_history[:-1]:
                hist.append(("human" if m["role"] == "user" else "ai", m["content"]))

            # Stream the agent's run live — show each tool call + result inside a
            # collapsible status block, then the final answer below.
            with st.chat_message("assistant"):
                collected_events: list[dict] = []
                final_text = ""
                with st.status("Working...", expanded=True) as status:
                    try:
                        for ev in st.session_state.agent.stream(user_q, chat_history=hist or None):
                            if ev["type"] == "reasoning":
                                st.markdown(f"💭 *{ev['content']}*")
                                collected_events.append(ev)
                            elif ev["type"] == "tool_call":
                                args_preview = ", ".join(f"{k}={v!r}" for k, v in ev["args"].items())
                                if len(args_preview) > 120:
                                    args_preview = args_preview[:120] + "…"
                                st.markdown(f"🔧 Calling **`{ev['name']}`**({args_preview})")
                                collected_events.append(ev)
                            elif ev["type"] == "tool_result":
                                preview = ev["content"]
                                if len(preview) > 400:
                                    preview = preview[:400] + f"… ({len(ev['content'])-400} more chars)"
                                st.markdown(f"✅ `{ev['name']}` returned:")
                                st.code(preview, language="text")
                                collected_events.append(ev)
                            elif ev["type"] == "final":
                                final_text = ev["content"]
                        status.update(label=f"Done — {len([e for e in collected_events if e['type']=='tool_call'])} tool call(s)",
                                      state="complete", expanded=False)
                    except Exception as e:
                        final_text = f"Agent error: {e}"
                        status.update(label="Failed", state="error", expanded=True)

                if final_text:
                    st.markdown(final_text)

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": final_text,
                "events": collected_events,
            })

        col_clear, _ = st.columns([1, 5])
        if col_clear.button("🧹 Clear chat"):
            st.session_state.chat_history = []
            st.rerun()


# ----------------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------------
st.divider()
st.caption(
    "Physics: 4 load cases per `Shock Isolator_850kg_4 Bayed 35U.xls` reference  ·  "
    "Catalog: Helical CB61400 / CB1400 / CB1500 / CB1700  ·  "
    "Agent: NVIDIA Llama 3.1 70B (tool calling)"
)
