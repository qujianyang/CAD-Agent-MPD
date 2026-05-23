"""
Agentic shock mount selection assistant.
LangChain tool-calling agent wrapping physics engine, catalog, CAD extractor, and RAG.
LLM: meta/llama-3.1-70b-instruct (NVIDIA API) — supports tool calling.
"""
import json
import os
from glob import glob
from typing import Optional

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from physics_engine import ShockEnv, run_analysis, format_report
from catalog import (
    ALL_CATALOGS, CB1400_CATALOG, CB1500_CATALOG, CB1800_CATALOG,
    select_and_analyze, format_selection_table, selection_context_for_llm,
)
from cad_compliance_checker import extract_cad_data as _extract_cad_data_raw

# Module-level state — set by ShockMountAgent.__init__ before tools are called
_api_key: Optional[str] = None
_rag: Optional[object] = None
_knowledge_embedder: Optional[object] = None
_knowledge_store: Optional[object] = None

KNOWLEDGE_STORE_PATH = "knowledge_embeddings.json"


def _get_rag():
    global _rag
    if _rag is None and _api_key:
        from mil_std_rag import MILStandardRAG
        _rag = MILStandardRAG(_api_key)
    return _rag


def _get_knowledge_search():
    """Lazy init the hierarchical knowledge store (knowledge/ folder)."""
    global _knowledge_embedder, _knowledge_store
    if _knowledge_store is None:
        from pathlib import Path
        from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore
        if not Path(KNOWLEDGE_STORE_PATH).exists():
            return None, None
        _knowledge_embedder = NVIDIAEmbedder(_api_key) if _api_key else None
        _knowledge_store    = JSONVectorStore(KNOWLEDGE_STORE_PATH)
    return _knowledge_embedder, _knowledge_store


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def extract_cad_data(assembly_script: str = "test_assembly.py") -> str:
    """
    Extract mass, CG, and bounding envelope from the active SolidWorks assembly.
    Returns mass_kg, CG coordinates (mm), and envelope dimensions (W/D/H in mm).
    Use this when you need the actual weight/mass of a CAD model before selecting an isolator.
    SolidWorks must be open with an assembly loaded.
    """
    props = _extract_cad_data_raw(assembly_script)
    if not props or not props.get("mass_kg"):
        return (
            "ERROR: Could not connect to SolidWorks or extract mass. "
            "Ensure SolidWorks is open with an assembly loaded. "
            "Ask the user to provide the mass manually instead."
        )
    lines = [
        "Extracted from SolidWorks:",
        f"  Mass      : {props.get('mass_kg')} kg",
        f"  Envelope  : W={props.get('width_mm','?')} x D={props.get('depth_mm','?')} x H={props.get('height_mm','?')} mm",
        f"  CG (note: coordinate origin may be uncalibrated): "
        f"X={props.get('cg_x','?')}, Y={props.get('cg_y','?')}, Z={props.get('cg_z','?')} mm",
    ]
    if props.get("components"):
        shown = props["components"][:6]
        lines.append(f"  Components ({props['component_count']}): {', '.join(shown)}"
                     + (" ..." if props["component_count"] > 6 else ""))
    # Embed raw props for downstream use
    lines.append(f"\nRAW_PROPS: {json.dumps(props)}")
    return "\n".join(lines)


@tool
def select_isolator(
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_s: float = 0.011,
    GT_limit_G: float = 10.0,
    series: str = "ALL",
) -> str:
    """
    Select the optimal wire rope isolator from the CB1400 / CB1500 / CB1800 catalog.
    Evaluates every matching part and recommends the SOFTEST (best isolation) that passes:
      - GT < GT_limit in all 3 load directions (compression vertical, lateral, shear)
      - Dynamic deflection < isolator's rated travel in all 3 directions
    Returns the full selection table plus mathematical proof for the recommended part.

    Args:
        mass_kg    : Total assembly mass in kg (get from extract_cad_data or ask user)
        n_bottom   : Number of bottom-mounted isolators (typical: 6 for a 4-bay rack)
        n_wall     : Number of wall-mounted isolators (typical: 4)
        Ao_G       : Shock magnitude in G (use 20G for MIL-STD-810 Category 4 off-road)
        to_s       : Shock pulse duration in seconds (use 0.011 for 11ms saw-tooth)
        GT_limit_G : Maximum allowable transmitted G (use 10G per MIL-STD-810)
        series     : Catalog filter — "ALL", "CB1400", "CB1500", or "CB1800"
    """
    catalog_map = {
        "CB1400": CB1400_CATALOG,
        "CB1500": CB1500_CATALOG,
        "CB1800": CB1800_CATALOG,
        "ALL":    ALL_CATALOGS,
    }
    catalog = catalog_map.get(series.upper(), ALL_CATALOGS)
    env = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)

    if mass_kg <= 0:
        return "ERROR: mass_kg must be a positive number. Ask the user for the assembly mass in kg, or call extract_cad_data to read it from SolidWorks."

    report, candidates = select_and_analyze(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        cad_props=None,     # CG coordinate calibration pending; mass-only for now
        shock_env=env,
        catalog=catalog,
    )

    valid = [c for c in candidates if c.valid]
    fail  = [c for c in candidates if not c.valid]
    rec   = valid[0] if valid else None

    # Lead with a clean, unambiguous answer block that the LLM can read reliably.
    lines = [
        "=== ISOLATOR SELECTION RESULT ===",
        f"Input:  mass={mass_kg} kg | mounts={n_bottom} bottom + {n_wall} wall | shock={Ao_G}G/{to_s*1000:.0f}ms | GT_limit={GT_limit_G}G",
        "",
    ]
    if rec:
        ld = rec.limiting_direction
        cb, cw, rw, rb = rec.comp_bottom, rec.comp_wall, rec.roll_wall, rec.roll_bottom
        lines += [
            f"RECOMMENDED: {rec.entry.part_no}  (Series {rec.entry.series})",
            f"  Size      : H={rec.entry.H_in}\" x W={rec.entry.W_in}\"",
            f"  K_comp    : {rec.entry.k_comp_lbin} lb/in",
            f"  K_shear   : {rec.entry.k_shear_lbin} lb/in",
            "",
            "  4 load cases (all must PASS — matches Excel ref):",
            f"    Comp-Bottom (Z,  vertical) : m={cb.m_kg:.1f} kg | fn={cb.fn_Hz:.2f} Hz | GT={cb.GT_G:.3f} G | dD={cb.delta_mm:.1f} mm  -> {'PASS' if cb.passed else 'FAIL'}",
            f"    Comp-Wall   (Y,  lateral)  : m={cw.m_kg:.1f} kg | fn={cw.fn_Hz:.2f} Hz | GT={cw.GT_G:.3f} G | dD={cw.delta_mm:.1f} mm  -> {'PASS' if cw.passed else 'FAIL'}",
            f"    Roll-Wall   (XZ, shear)    : m={rw.m_kg:.1f} kg | fn={rw.fn_Hz:.2f} Hz | GT={rw.GT_G:.3f} G | dD={rw.delta_mm:.1f} mm  -> {'PASS' if rw.passed else 'FAIL'}",
            f"    Roll-Bottom (XY, shear)    : m={rb.m_kg:.1f} kg | fn={rb.fn_Hz:.2f} Hz | GT={rb.GT_G:.3f} G | dD={rb.delta_mm:.1f} mm  -> {'PASS' if rb.passed else 'FAIL'}",
            f"  Limiting direction: {ld.label} (GT ratio: {ld.GT_G/ld.GT_limit:.0%} of limit)",
            "",
        ]
        if len(valid) > 1:
            lines.append(f"  Also valid (softer = better isolation, but available): {', '.join(c.entry.part_no for c in valid[1:])}")
    else:
        lines.append("NO VALID PART FOUND. Increase number of mounts or relax GT limit.")

    lines += [
        "",
        f"Parts that FAIL ({len(fail)}): {', '.join(c.entry.part_no for c in fail[:8])}{'...' if len(fail) > 8 else ''}",
        "=================================",
    ]
    return "\n".join(lines)


@tool
def run_shock_analysis(
    mass_kg: float,
    part_no: str = "CB1400-15",
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_s: float = 0.011,
    GT_limit_G: float = 10.0,
) -> str:
    """
    Verify whether a specific isolator part passes shock analysis for a given mass.
    Calculates: fn (natural frequency, Hz), GT (transmitted G), dD (dynamic deflection, mm).
    Use this to confirm the recommended part, or to test a user-specified part number.

    Args:
        mass_kg    : Total assembly mass in kg
        part_no    : Isolator part number, e.g. 'CB1400-15', 'CB1500-30', 'CB1800-20'
        n_bottom   : Number of bottom-mounted isolators (default 6)
        n_wall     : Number of wall-mounted isolators (default 4)
        Ao_G       : Shock magnitude in G (default 20G)
        to_s       : Shock pulse duration in seconds (default 0.011s = 11ms)
        GT_limit_G : Maximum allowable transmitted G (default 10G)
    """
    entry = next((e for e in ALL_CATALOGS if e.part_no == part_no), None)
    if entry is None:
        available = sorted({e.part_no for e in ALL_CATALOGS})
        return (
            f"ERROR: Part '{part_no}' not found in catalog.\n"
            f"Available parts: {', '.join(available)}"
        )
    spec = entry.to_isolator_spec()
    env  = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)
    report = run_analysis(mass_kg, n_bottom, n_wall, shock_env=env, isolator=spec)
    return format_report(report)


@tool
def lookup_knowledge(query: str, parent_topic: str = "") -> str:
    """
    Search the hierarchical engineering knowledge base (knowledge/ folder).

    Available parent topics: 'shock_mount' (more topics coming soon).
    Inside shock_mount/ there are pages: formulas, load_cases, selection_rules,
    catalog_overview.

    Use this when you need to cite EXACT formulas (V, fn, GT, dD), explain WHY
    the mass is divided differently per load case, justify the "softest valid
    part" selection rule, or quote stiffness/travel values from the CB catalogs.

    Args:
        query:         What you want to know, in natural language.
                       Examples: "GT formula", "why divide mass by 2",
                       "when to use CB1800", "what passes for 1500kg".
        parent_topic:  Optional filter — e.g. "shock_mount". Leave empty to
                       search across all topics.

    Returns the top matching pages with topic labels so they can be cited.
    """
    embedder, store = _get_knowledge_search()
    if store is None:
        return ("ERROR: knowledge base not built yet. Run `python setup_knowledge.py` "
                "to ingest the knowledge/ folder.")
    if embedder is None:
        return "ERROR: NVIDIA API key not set; cannot embed query."

    parent = parent_topic.strip() or None
    try:
        q_emb = embedder.embed_text(query)
    except Exception as e:
        return f"ERROR: failed to embed query: {e}"

    hits = store.search(q_emb, top_k=3, parent_topic=parent)
    if not hits:
        msg = f"No matching pages for query '{query}'"
        if parent:
            msg += f" within parent_topic='{parent}'"
        return msg

    parts = [f"Knowledge base hits for '{query}'"
             + (f" (filtered to parent_topic={parent!r})" if parent else "")
             + ":"]
    for i, h in enumerate(hits, 1):
        label = f"{h.get('parent_topic','?')}/{h.get('child_name','?')}"
        parts.append(
            f"\n--- [{i}] {label}  ({h['similarity']:.0%} match)  ---\n"
            f"Title: {h.get('title','(no title)')}\n"
            f"Source: {h.get('source_path','?')}\n"
            f"{h['content']}\n"
        )
    return "\n".join(parts)


@tool
def list_cad_files(directory: str = ".") -> str:
    """
    List available SolidWorks assembly files (.SLDASM) in a directory.
    Returns paths that can be passed to extract_cad_data to load a specific assembly.
    Args:
        directory: Directory path to search (default: current working directory)
    """
    files: list[str] = []
    for pattern in (f"{directory}/**/*.SLDASM", f"{directory}/**/*.sldasm"):
        files.extend(glob(pattern, recursive=True))

    if not files:
        return f"No .SLDASM files found in '{directory}'. Check the directory path."
    return f"Found {len(files)} SolidWorks assemblies:\n" + "\n".join(f"  {f}" for f in files)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a mechanical engineering design assistant specializing in shock isolation \
for military vehicle-mounted shelter equipment.

Your primary task: select the correct wire rope isolator (CB1400, CB1500, CB1800 series) \
for equipment racks given mass, mount configuration, and shock environment.

Standard defaults (use unless the user specifies otherwise):
- Shock profile : 20G, 11ms saw-tooth (MIL-STD-810H Category 4 off-road)
- GT limit      : 10G transmitted
- Mount config  : 6 bottom + 4 wall isolators (typical 4-bay rack)

Workflow for isolator selection:
1. Confirm or extract the assembly mass (use extract_cad_data if SolidWorks is open, \
   otherwise ask the user)
2. Confirm mount configuration (n_bottom, n_wall)
3. Call select_isolator — it evaluates the entire catalog and returns the recommendation
4. Summarise the result: part number, series, K values, fn, GT, dD

Always show key numbers. Never invent stiffness values or GT results — \
call the tools to compute them.
"""


class ShockMountAgent:
    """LangChain tool-calling agent for shock mount selection."""

    _TOOLS = [
        extract_cad_data,
        select_isolator,
        run_shock_analysis,
        lookup_knowledge,
        list_cad_files,
    ]

    def __init__(self, api_key: str):
        global _api_key
        _api_key = api_key

        llm = ChatNVIDIA(
            model="meta/llama-3.1-70b-instruct",
            api_key=api_key,
            temperature=0.1,
            max_tokens=2048,
        )

        # LangChain 1.x: create_agent returns a compiled LangGraph
        self._agent = create_agent(llm, self._TOOLS, system_prompt=_SYSTEM_PROMPT)

    def invoke(self, question: str, chat_history: list | None = None) -> str:
        messages = list(chat_history) if chat_history else []
        messages.append(("human", question))
        result = self._agent.invoke({"messages": messages})
        # Final answer is the last AI message
        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: Set NVIDIA_API_KEY in your .env file or environment.")

    agent = ShockMountAgent(api_key)
    print("Shock Mount Agent ready. Type 'quit' to exit.\n")
    history: list = []

    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            break

        response = agent.invoke(q, chat_history=history if history else None)
        print(f"\nAgent: {response}\n")

        # Maintain a rolling 6-message history (3 exchanges)
        from langchain_core.messages import HumanMessage, AIMessage
        # Keep last 3 exchanges in history (6 messages)
        history.append(("human", q))
        history.append(("ai", response))
        if len(history) > 6:
            history = history[-6:]
