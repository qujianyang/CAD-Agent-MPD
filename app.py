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
from physics_engine import ShockEnv
from catalog import (
    ALL_CATALOGS, CB1400_CATALOG, CB1500_CATALOG, CB1800_CATALOG,
    select_and_analyze, format_selection_table, format_report,
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
    "All series (CB1400 + CB1500 + CB1800)": ALL_CATALOGS,
    "CB1400 (1/2\" wire, ~200-1000 kg)":    CB1400_CATALOG,
    "CB1500 (5/8\" wire, ~500-1800 kg)":    CB1500_CATALOG,
    "CB1800 (1\" wire, ~1000-3000 kg)":     CB1800_CATALOG,
}


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
def _init_state():
    defaults = {
        "cad_props":   None,
        "raw_output":  "",
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
def run_solidworks_extraction(script: str = "test_assembly.py") -> tuple[dict, str]:
    """Run test_assembly.py in a subprocess; return (parsed props, raw stdout)."""
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )
    return _parse_cad_output(result.stdout), result.stdout


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
    st.subheader("Manual Isolator Selector")
    st.caption("Enter the assembly mass directly. Useful when SolidWorks isn't running "
               "or you're working from spec sheets.")

    c1, c2 = st.columns([1, 1])
    with c1:
        mass_kg = st.number_input("Total assembly mass [kg]", value=850.0,
                                  min_value=1.0, max_value=10000.0, step=10.0, key="q_mass")
    with c2:
        series_label = st.selectbox("Catalog filter", list(SERIES_MAP.keys()), key="q_series")

    st.markdown("**Mount configuration**")
    n_bot, n_wall = _mount_widget("q", default_bot=6, default_wall=4)

    st.markdown("**Shock environment**")
    env = _shock_env_widget("q")

    if st.button("🎯 Select Best Isolator", type="primary",
                 use_container_width=True, key="q_run"):
        with st.spinner("Running 4-case selection..."):
            report, candidates = select_and_analyze(
                mass_kg   = mass_kg,
                n_bottom  = n_bot,
                n_wall    = n_wall,
                cad_props = None,
                shock_env = env,
                catalog   = SERIES_MAP[series_label],
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
        st.markdown("**Mount configuration**")
        n_bot_cad, n_wall_cad = _mount_widget("cad", default_bot=6, default_wall=4)

        st.markdown("**Shock environment**")
        env_cad = _shock_env_widget("cad")

        if st.button("🔌 Extract from SolidWorks", type="primary",
                     use_container_width=True, key="cad_extract"):
            with st.spinner("Talking to SolidWorks via COM..."):
                props, raw = run_solidworks_extraction()
                st.session_state.cad_props = props
                st.session_state.raw_output = raw

    with col_right:
        props = st.session_state.cad_props
        if not props or not props.get("mass_kg"):
            st.info("Run extraction (left). SolidWorks must be open with the target "
                    "assembly. If SolidWorks isn't available, use **Quick Selector** instead.")
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
        # Lazy-init the agent (slow first time — loads NVIDIA endpoint)
        if st.session_state.agent is None:
            with st.spinner("Initializing agent (Llama 3.1 70B + 5 tools)..."):
                try:
                    from agent import ShockMountAgent
                    st.session_state.agent = ShockMountAgent(API_KEY)
                except Exception as e:
                    st.error(f"Failed to initialize agent: {e}")

        # Render conversation history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # New user input
        user_q = st.chat_input("Ask anything (e.g. 'what isolator for 1200kg, 6+4 mounts?')")
        if user_q and st.session_state.agent is not None:
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            # Build LangChain-style chat history from prior messages
            hist = []
            for m in st.session_state.chat_history[:-1]:
                hist.append(("human" if m["role"] == "user" else "ai", m["content"]))

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        reply = st.session_state.agent.invoke(user_q, chat_history=hist or None)
                    except Exception as e:
                        reply = f"Agent error: {e}"
                st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})

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
    "Catalog: VMC CB1400 / CB1500 / CB1800  ·  "
    "Agent: NVIDIA Llama 3.1 70B (tool calling)"
)
