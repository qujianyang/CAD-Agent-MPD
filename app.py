"""
Streamlit UI for CAD-Aware Engineering Design Assistant.

Run with:
    streamlit run app.py
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st

from cad_compliance_checker import _parse_cad_output
from mil_std_rag import MILStandardRAG


# ---------- Page config ----------
st.set_page_config(
    page_title="Design Assistant",
    page_icon="🔧",
    layout="wide",
)

load_dotenv()
API_KEY = os.environ.get(
    "NVIDIA_API_KEY",
    "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",
)


# ---------- Helpers ----------
def run_solidworks_extraction(assembly_script: str = "test_assembly.py") -> tuple[dict, str]:
    """Run test_assembly.py in subprocess, return (parsed_props, raw_stdout)."""
    result = subprocess.run(
        [sys.executable, assembly_script],
        capture_output=True,
        text=True,
    )
    return _parse_cad_output(result.stdout), result.stdout


# ---------- Session state init ----------
if "cad_props" not in st.session_state:
    st.session_state.cad_props = None
if "raw_output" not in st.session_state:
    st.session_state.raw_output = ""
if "last_response" not in st.session_state:
    st.session_state.last_response = ""


# ---------- Header ----------
st.title("🔧 Design Assistant")
st.caption("Bridge live SolidWorks CAD data with shock-mount catalogs via RAG + LLM")

if not Path("mil_std_embeddings.json").exists():
    st.error("Vector store `mil_std_embeddings.json` not found. Run `python setup_rag.py` first.")
    st.stop()


# ---------- Layout: two columns ----------
left, right = st.columns([1, 1])

# ---------- LEFT: CAD extraction ----------
with left:
    st.header("1️⃣  CAD Data Extraction")
    st.write("Connect to SolidWorks and pull live geometry from the active assembly.")

    if st.button("🔌 Connect & Extract", type="primary", use_container_width=True):
        with st.spinner("Talking to SolidWorks via COM API..."):
            props, raw = run_solidworks_extraction()
            st.session_state.cad_props = props
            st.session_state.raw_output = raw

    props = st.session_state.cad_props
    if props:
        st.success(f"Extracted {len(props)} properties")

        c1, c2, c3 = st.columns(3)
        c1.metric("Mass", f"{props.get('mass_kg', 0):.1f} kg")
        c2.metric("Volume", f"{props.get('volume_mm3', 0)/1e6:.1f} cm³")
        c3.metric("Surface", f"{props.get('surface_mm2', 0)/1e6:.2f} m²")

        st.subheader("Envelope (W × D × H)")
        st.code(f"{props.get('width_mm','?')} × {props.get('depth_mm','?')} × {props.get('height_mm','?')} mm")

        st.subheader("Center of Mass")
        st.code(
            f"X = {props.get('cg_x','?')} mm\n"
            f"Y = {props.get('cg_y','?')} mm\n"
            f"Z = {props.get('cg_z','?')} mm"
        )

        if props.get("components"):
            st.subheader(f"BOM ({props.get('component_count')} components)")
            for c in props["components"]:
                st.write(f"• {c}")

        with st.expander("Raw SolidWorks output"):
            st.text(st.session_state.raw_output)
    else:
        st.info("Click **Connect & Extract** to start. Make sure SolidWorks is open with the target assembly.")


# ---------- RIGHT: Question + RAG ----------
with right:
    st.header("2️⃣  Engineering Question")

    default_q = (
        "Based on the mass and CG height, what shock mount or isolator is recommended "
        "for off-road vehicular vibration?"
    )
    question = st.text_area("Ask the AI engineer:", value=default_q, height=120)

    disabled = st.session_state.cad_props is None
    if st.button("🧠 Get Recommendation", type="primary", use_container_width=True, disabled=disabled):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Retrieving catalog sections + querying LLM..."):
                rag = MILStandardRAG(API_KEY)
                response = rag.query_compliance(st.session_state.cad_props, question)
                st.session_state.last_response = response

    if disabled:
        st.warning("Extract CAD data first (left panel).")

    st.header("3️⃣  Recommendation")
    if st.session_state.last_response:
        st.markdown(st.session_state.last_response)
    else:
        st.info("LLM response will appear here.")


# ---------- Footer ----------
st.divider()
st.caption("Built with NVIDIA Nemotron embeddings + LangChain + Streamlit · FYP 2026")
