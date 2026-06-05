"""
Agentic shock mount selection assistant.
LangChain tool-calling agent wrapping physics engine, catalog, CAD extractor, and RAG.
LLM: meta/llama-3.1-70b-instruct (NVIDIA API) — supports tool calling.
"""
import json
import os
from glob import glob
from typing import Optional

# MLflow tracing is OPT-IN and fully decoupled. The agent never touches MLflow
# unless you explicitly call enable_mlflow_tracing(). By default there is zero
# MLflow involvement (no import, no server connection, no startup cost).
_MLFLOW_ON = False


def enable_mlflow_tracing(uri: str = "http://localhost:5000",
                          experiment: str = "CAD-Agent-MPD") -> bool:
    """Manually turn on MLflow autologging. Call this yourself when you want to
    trace; otherwise the agent runs with no MLflow at all. Returns True if on."""
    global _MLFLOW_ON
    try:
        import mlflow
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        mlflow.langchain.autolog()
        _MLFLOW_ON = True
        print(f"[agent] MLflow tracing enabled → {uri}")
    except Exception as e:
        _MLFLOW_ON = False
        print(f"[agent] could not enable MLflow tracing: {e}")
    return _MLFLOW_ON


from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from physics_engine import ShockEnv, run_analysis, format_report
from catalog import (
    ALL_CATALOGS,
    CB61400_CATALOG, CB1400_CATALOG, CB1500_CATALOG, CB1700_CATALOG,
    select_and_analyze, format_selection_table, selection_context_for_llm,
)
from cad_compliance_checker import extract_cad_data as _extract_cad_data_raw
from tiedown_tools import (
    run_tiedown_check, recommend_fasteners, flag_critical_items, _TIEDOWN_PROMPT,
)
from mobility_tools import (
    run_mobility_check, slope_limit, cornering_check, flag_unstable,
    _MOBILITY_PROMPT, _MOBILITY_TOOLS,
)

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
def extract_cad_data(cad_file_path: str = "") -> str:
    """
    Extract mass, CG, and bounding envelope from a SolidWorks assembly or part.

    Args:
        cad_file_path: Absolute path to a .SLDASM or .SLDPRT file (e.g.
                       "C:\\path\\to\\Rack.SLDASM"). Leave empty to use the
                       currently active SolidWorks document. If you don't know
                       a path, call list_cad_files first to discover available
                       files, then pass the chosen path here.

    Returns mass_kg, CG (in both default origin and base-relative frames),
    envelope dimensions (W/D/H mm), and BOM. SolidWorks must be installed and
    running on the host.
    """
    props = _extract_cad_data_raw(file_path=cad_file_path or None)
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
    Select the optimal wire rope isolator from the CB61400 / CB1400 / CB1500 / CB1700 catalog.
    Evaluates every matching part and recommends the SOFTEST (best isolation) that passes:
      - GT < GT_limit in all 3 load directions (compression vertical, lateral, shear)
      - Dynamic deflection < isolator's rated travel in all 3 directions
    Returns the full selection table plus mathematical proof for the recommended part.

    IMPORTANT — parameter handling:
    Only pass values for parameters the user explicitly specifies. For everything
    else, OMIT the parameter so the project default applies. Do NOT guess and do
    NOT pass 0 for the shock parameters — 0 makes the physics trivial.

    Project defaults (used if you omit the parameter):
        n_bottom=6, n_wall=4, Ao_G=20.0G, to_s=0.011s (11ms),
        GT_limit_G=10.0G, series="ALL"

    Args:
        mass_kg    : REQUIRED. Total assembly mass in kg. Get from extract_cad_data
                     or ask the user.
        n_bottom   : Number of bottom-mounted isolators. Default 6. OMIT unless user says.
        n_wall     : Number of wall-mounted isolators. Default 4. OMIT unless user says.
        Ao_G       : Shock magnitude in G. Default 20.0 (MIL-STD-810H Category 4).
                     OMIT unless user explicitly gives a different shock spec.
        to_s       : Shock pulse duration in seconds. Default 0.011 (11ms saw-tooth).
                     OMIT unless user explicitly gives a different pulse duration.
        GT_limit_G : Max allowable transmitted G. Default 10.0 G. OMIT unless user says.
        series     : Catalog filter. "ALL", "CB61400", "CB1400", "CB1500", or "CB1700". Default "ALL".
    """
    catalog_map = {
        "CB1400": CB1400_CATALOG,
        "CB1500": CB1500_CATALOG,
        "CB61400": CB61400_CATALOG,
        "CB1700": CB1700_CATALOG,
        "ALL":    ALL_CATALOGS,
    }
    catalog = catalog_map.get(series.upper(), ALL_CATALOGS)

    if mass_kg <= 0:
        return "ERROR: mass_kg must be a positive number. Ask the user for the assembly mass in kg, or call extract_cad_data to read it from SolidWorks."

    # Safety net: the LLM sometimes passes 0 or negative values for shock params
    # (it truncates 0.011 -> "0"). Clamp to defaults and tell everyone what we did.
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted default 20.0 G")
        Ao_G = 20.0
    if to_s is None or to_s <= 0:
        substitutions.append(f"to_s was {to_s!r} (invalid); substituted default 0.011 s (11 ms)")
        to_s = 0.011
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0

    env = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)

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
    lines = []
    if substitutions:
        lines.append("NOTE: Tool received invalid shock parameter(s). Substituted defaults:")
        for s in substitutions:
            lines.append(f"  - {s}")
        lines.append("")
    lines += [
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

    IMPORTANT — parameter handling:
    Only pass values the user explicitly specifies. OMIT all other parameters
    so the project defaults apply. Do NOT pass 0 for shock parameters — 0 makes
    the physics trivial (every part passes).

    Project defaults (used if you omit the parameter):
        n_bottom=6, n_wall=4, Ao_G=20.0G, to_s=0.011s (11ms), GT_limit_G=10.0G

    Args:
        mass_kg    : REQUIRED. Total assembly mass in kg.
        part_no    : REQUIRED. Isolator part number, e.g. 'CB1400-15', 'CB1500-30'.
        n_bottom   : Bottom-mount count. Default 6. OMIT unless user says.
        n_wall     : Wall-mount count.   Default 4. OMIT unless user says.
        Ao_G       : Shock magnitude in G. Default 20.0. OMIT unless user specifies.
        to_s       : Shock pulse duration (seconds). Default 0.011. OMIT unless user specifies.
        GT_limit_G : Max allowable transmitted G. Default 10.0. OMIT unless user says.
    """
    entry = next((e for e in ALL_CATALOGS if e.part_no == part_no), None)
    if entry is None:
        available = sorted({e.part_no for e in ALL_CATALOGS})
        return (
            f"ERROR: Part '{part_no}' not found in catalog.\n"
            f"Available parts: {', '.join(available)}"
        )

    # Same safety net as select_isolator — clamp bad shock params to defaults
    # and tell the caller what we changed so it shows up in the chat trace.
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted default 20.0 G")
        Ao_G = 20.0
    if to_s is None or to_s <= 0:
        substitutions.append(f"to_s was {to_s!r} (invalid); substituted default 0.011 s (11 ms)")
        to_s = 0.011
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0

    spec = entry.to_isolator_spec()
    env  = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)
    report = run_analysis(mass_kg, n_bottom, n_wall, shock_env=env, isolator=spec)
    body = format_report(report)
    if substitutions:
        note = "NOTE: Tool received invalid shock parameter(s). Substituted defaults:\n"
        for s in substitutions:
            note += f"  - {s}\n"
        return note + "\n" + body
    return body


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

@tool
def find_capacity_limit(
    part_no: str,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_s: float = 0.011,
    GT_limit_G: float = 10.0,
) -> str:
    """
    Find the mass range where a specific isolator part passes all 4 load cases.

    Use this when the user asks "what's the maximum / heaviest mass this part
    can support?", "what's the valid range for this isolator?", or "at what
    mass does this part fail?". This tool answers questions that a single
    run_shock_analysis call cannot — it sweeps the mass axis with binary
    search to find both the LOWER and UPPER boundaries of the valid range.

    Physics intuition (why there are two boundaries):
      - At low mass: fn is high -> GT exceeds limit (transmitted shock too high)
      - At high mass: dD exceeds the isolator's rated travel (too much deflection)
      - In between: valid range

    Args:
        part_no   : REQUIRED. Isolator part number, e.g. 'CB1400-30'.
        n_bottom  : Bottom-mount count. Default 6. OMIT unless user specifies.
        n_wall    : Wall-mount count.   Default 4. OMIT unless user specifies.
        Ao_G      : Shock magnitude in G. Default 20.0. OMIT unless user specifies.
        to_s      : Shock pulse duration (s). Default 0.011. OMIT unless user specifies.
        GT_limit_G: Max allowable transmitted G. Default 10.0. OMIT unless user specifies.

    Returns mass range as "X kg <= M <= Y kg" plus the limiting failure reason
    at each boundary (which direction failed and by how much).
    """
    entry = next((e for e in ALL_CATALOGS if e.part_no == part_no), None)
    if entry is None:
        available = sorted({e.part_no for e in ALL_CATALOGS})
        return (
            f"ERROR: Part '{part_no}' not found in catalog.\n"
            f"Available parts: {', '.join(available)}"
        )

    # Same safety net as the other tools
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted default 20.0 G")
        Ao_G = 20.0
    if to_s is None or to_s <= 0:
        substitutions.append(f"to_s was {to_s!r} (invalid); substituted default 0.011 s")
        to_s = 0.011
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0

    spec = entry.to_isolator_spec()
    env  = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)

    def _eval(mass_kg: float):
        """Return (all_passed: bool, report: PhysicsReport | None)."""
        if mass_kg <= 0:
            return False, None
        try:
            r = run_analysis(mass_kg, n_bottom, n_wall, shock_env=env, isolator=spec)
            return r.all_passed, r
        except Exception:
            return False, None

    def _failure_reason(report) -> str:
        """Short string describing the FIRST failing direction."""
        if not report:
            return "(no report)"
        failed = [d for d in report.directions if not d.passed]
        if not failed:
            return "(no failure)"
        d = failed[0]
        bits = []
        if not d.GT_ok:
            bits.append(f"GT={d.GT_G:.2f}G > limit {d.GT_limit}G")
        if not d.delta_ok:
            bits.append(f"dD={d.delta_mm:.1f}mm > limit {d.delta_limit_mm:.1f}mm")
        return f"{d.label}: " + " AND ".join(bits)

    SEARCH_LO = 1.0       # min mass to consider (kg)
    SEARCH_HI = 20000.0   # max mass to consider (kg)
    PRECISION = 1.0       # binary-search to within 1 kg

    # 1. Find an anchor mass that DOES pass (so we know the bracket is non-empty)
    sample_points = [50, 200, 500, 1000, 2000, 5000, 10000]
    anchor: float | None = None
    for m in sample_points:
        ok, _ = _eval(m)
        if ok:
            anchor = float(m)
            break

    if anchor is None:
        # Part doesn't pass at any sample point. Run at one mid-point and report why.
        _, r = _eval(1000.0)
        why = _failure_reason(r)
        return (
            f"=== CAPACITY ANALYSIS: {part_no} ===\n"
            f"Config: {n_bottom} bottom + {n_wall} wall mounts | Shock: {Ao_G}G/{to_s*1000:.0f}ms | GT limit: {GT_limit_G}G\n\n"
            f"NO valid mass found in {SEARCH_LO:.0f}-{SEARCH_HI:.0f} kg range.\n"
            f"At 1000 kg: FAIL — {why}\n\n"
            f"Try: a softer part (lower K), more mounts, or a looser GT limit."
        )

    # 2. Binary-search downward for the LOWER bound (M_min)
    ok_floor, _ = _eval(SEARCH_LO)
    if ok_floor:
        M_min = SEARCH_LO
        M_min_reason = f"(passes even at {SEARCH_LO:.0f} kg — no effective lower limit)"
    else:
        lo, hi = SEARCH_LO, anchor
        while hi - lo > PRECISION:
            mid = (lo + hi) / 2.0
            ok, _ = _eval(mid)
            if ok:
                hi = mid
            else:
                lo = mid
        M_min = hi
        _, r_below = _eval(max(SEARCH_LO, M_min - PRECISION * 2))
        M_min_reason = _failure_reason(r_below)

    # 3. Binary-search upward for the UPPER bound (M_max)
    ok_ceil, _ = _eval(SEARCH_HI)
    if ok_ceil:
        M_max = SEARCH_HI
        M_max_reason = f"(passes even at {SEARCH_HI:.0f} kg — no effective upper limit)"
    else:
        lo, hi = anchor, SEARCH_HI
        while hi - lo > PRECISION:
            mid = (lo + hi) / 2.0
            ok, _ = _eval(mid)
            if ok:
                lo = mid
            else:
                hi = mid
        M_max = lo
        _, r_above = _eval(M_max + PRECISION * 2)
        M_max_reason = _failure_reason(r_above)

    # 4. Format the result
    lines: list[str] = []
    if substitutions:
        lines.append("NOTE: Tool received invalid shock parameter(s). Substituted defaults:")
        for s in substitutions:
            lines.append(f"  - {s}")
        lines.append("")
    lines += [
        f"=== CAPACITY ANALYSIS: {part_no} (Series {entry.series}) ===",
        f"Config: {n_bottom} bottom + {n_wall} wall mounts",
        f"Shock : {Ao_G}G / {to_s*1000:.0f}ms saw-tooth",
        f"GT limit: {GT_limit_G}G | Travel limits: dmax_comp={entry.d_max_comp_mm:.1f}mm, dmax_shear={entry.d_max_shear_mm:.1f}mm",
        "",
        f"Valid mass range: {M_min:.0f} kg <= M <= {M_max:.0f} kg",
        "",
        f"  LOWER bound = {M_min:.0f} kg",
        f"    Below this, part FAILS: {M_min_reason}",
        f"  UPPER bound = {M_max:.0f} kg",
        f"    Above this, part FAILS: {M_max_reason}",
    ]
    return "\n".join(lines)


@tool
def filter_by_deflection(
    mass_kg: float,
    max_dD_mm: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_s: float = 0.011,
    GT_limit_G: float = 10.0,
    series: str = "ALL",
) -> str:
    """
    List isolator parts that BOTH pass the 4-case shock analysis AND keep
    dynamic deflection below a user-specified clearance limit.

    Use this when the user mentions a physical deflection / clearance
    constraint that is stricter than the isolator's own rated travel —
    for example:
      "I have only 30 mm clearance above the rack..."
      "Tight side clearance — what part keeps dD under 20 mm?"
      "Which CB1400 parts deflect less than 50 mm for 850 kg?"

    Standard selection (`select_isolator`) only checks each part against its
    OWN rated dmax. This tool adds a SECOND, stricter ΔD limit set by the
    user's installation geometry, and returns the full list of qualifying
    parts (not just the softest one).

    Args:
        mass_kg    : REQUIRED. Total assembly mass in kg.
        max_dD_mm  : REQUIRED. Maximum allowable dynamic deflection (mm).
                     This is the user's installation clearance, NOT the
                     isolator's vendor-rated travel.
        n_bottom   : Bottom-mount count. Default 6. OMIT unless user says.
        n_wall     : Wall-mount count.   Default 4. OMIT unless user says.
        Ao_G       : Shock magnitude in G. Default 20.0. OMIT unless user says.
        to_s       : Shock pulse duration (s). Default 0.011. OMIT unless user says.
        GT_limit_G : Maximum transmitted G. Default 10.0. OMIT unless user says.
        series     : Catalog filter. "ALL", "CB61400", "CB1400", "CB1500", or "CB1700". Default "ALL".

    Returns the qualifying parts sorted softest-K first (best isolation that
    still fits the clearance), plus a list of parts that pass the 4-case
    shock analysis but exceed the user's clearance.
    """
    if mass_kg <= 0:
        return "ERROR: mass_kg must be a positive number."
    if max_dD_mm <= 0:
        return "ERROR: max_dD_mm must be a positive number."

    # Same shock-param safety net
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted 20.0 G")
        Ao_G = 20.0
    if to_s is None or to_s <= 0:
        substitutions.append(f"to_s was {to_s!r} (invalid); substituted 0.011 s")
        to_s = 0.011
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted 10.0 G")
        GT_limit_G = 10.0

    catalog_map = {
        "CB1400": CB1400_CATALOG,
        "CB1500": CB1500_CATALOG,
        "CB61400": CB61400_CATALOG,
        "CB1700": CB1700_CATALOG,
        "ALL":    ALL_CATALOGS,
    }
    catalog = catalog_map.get(series.upper(), ALL_CATALOGS)
    env = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G)

    _, candidates = select_and_analyze(
        mass_kg   = mass_kg,
        n_bottom  = n_bottom,
        n_wall    = n_wall,
        cad_props = None,
        shock_env = env,
        catalog   = catalog,
    )

    # Bucket each candidate
    qualifying:    list[tuple] = []   # passes 4-case AND worst dD <= max_dD_mm
    over_clearance:list[tuple] = []   # passes 4-case BUT worst dD > max_dD_mm
    fails_shock:   list[str]   = []   # fails 4-case shock analysis

    for c in candidates:
        worst_dD = max(d.delta_mm for d in c._dirs)
        worst_GT = max(d.GT_G    for d in c._dirs)
        if c.valid:
            row = (c.entry, worst_GT, worst_dD)
            if worst_dD <= max_dD_mm:
                qualifying.append(row)
            else:
                over_clearance.append(row)
        else:
            fails_shock.append(c.entry.part_no)

    # Sort: qualifying by softest K first; over-clearance by closest-to-limit first
    qualifying.sort(key=lambda r: r[0].k_comp_lbin)
    over_clearance.sort(key=lambda r: r[2])  # ascending dD

    lines: list[str] = []
    if substitutions:
        lines.append("NOTE: substituted defaults for invalid shock parameter(s):")
        for s in substitutions:
            lines.append(f"  - {s}")
        lines.append("")
    lines += [
        "=== DEFLECTION-CONSTRAINED SELECTION ===",
        f"Input: mass={mass_kg} kg | mounts={n_bottom}+{n_wall} | "
        f"shock={Ao_G}G/{to_s*1000:.0f}ms | GT_limit={GT_limit_G}G",
        f"Extra constraint: worst-case dD must be <= {max_dD_mm:.1f} mm",
        "",
    ]

    if qualifying:
        lines.append(f"QUALIFYING PARTS ({len(qualifying)} parts pass shock AND clearance):")
        lines.append("  (sorted softest first — best isolation that still fits)")
        for entry, gt, dD in qualifying:
            lines.append(
                f"  {entry.part_no:12s} | K_comp={entry.k_comp_lbin:>5.0f} lb/in | "
                f"worst GT={gt:>5.2f} G | worst dD={dD:>5.1f} mm"
            )
        lines.append("")
        lines.append(f"RECOMMENDED: {qualifying[0][0].part_no} "
                     f"(softest K that keeps dD <= {max_dD_mm:.1f} mm)")
    else:
        lines.append(f"NO part passes both shock analysis AND dD <= {max_dD_mm:.1f} mm.")
        lines.append("Try: increase clearance, increase mount count, "
                     "or relax shock spec.")

    if over_clearance:
        lines.append("")
        lines.append(f"Parts that PASS shock but EXCEED the {max_dD_mm:.1f} mm clearance "
                     f"(showing first 8 by ascending dD):")
        for entry, gt, dD in over_clearance[:8]:
            over_by = dD - max_dD_mm
            lines.append(
                f"  {entry.part_no:12s} | worst dD={dD:>5.1f} mm  (over by {over_by:>5.1f} mm)"
            )

    if fails_shock:
        lines.append("")
        lines.append(f"Parts that FAIL 4-case shock analysis ({len(fails_shock)}): "
                     + ", ".join(fails_shock[:10])
                     + ("..." if len(fails_shock) > 10 else ""))

    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a mechanical engineering design assistant specializing in shock isolation \
for military vehicle-mounted shelter equipment.

You act as an ENGINEERING JUDGE, not a tool dispatcher. Your job is to interpret \
the numbers the tools give you, cite the engineering rule you applied, and actively \
flag concerns the user implied but did not state. Do NOT just paraphrase the tool output.

Your primary task: select the correct wire rope isolator (CB61400, CB1400, CB1500, \
CB1700 series) for equipment racks given mass, mount configuration, and shock environment.

Standard defaults (used automatically if you omit the parameter — see CRITICAL rule below):
- Shock profile : 20G, 11ms saw-tooth (MIL-STD-810H Category 4 off-road)
- GT limit      : 10G transmitted
- Mount config  : 6 bottom + 4 wall isolators (typical 4-bay rack)

CRITICAL — parameter passing rule for ALL tools:
- Only pass values for parameters the user EXPLICITLY mentions.
- For every other parameter, OMIT it from the tool call so the project default applies.
- Never pass 0 or "0" for shock parameters (Ao_G, to_s, GT_limit_G). Passing 0
  makes the physics trivial and the result meaningless.
- Numeric parameters: pass real numbers (e.g. 0.011, 20.0), never strings of
  truncated numbers (e.g. "0" instead of "0.011").

==========================================================================
WORKFLOW FOR ISOLATOR SELECTION QUESTIONS (mandatory two-call pattern)
==========================================================================
1. Confirm or extract the assembly mass (use extract_cad_data if SolidWorks is \
   open, otherwise ask the user).
2. Confirm mount configuration only if the user specified one (else omit).
3. Call select_isolator with ONLY the parameters the user gave you.
4. MANDATORY: call lookup_knowledge to retrieve the engineering rule you are \
   about to cite. Pick a query that matches the situation:
     - "softest valid part selection rule" — for the recommendation rationale
     - "saw-tooth pulse MIL-STD-810"        — for the shock profile attribution
     - "deflection clearance"                — when dD is the limiting case
     - "when no part passes"                 — when select_isolator finds no valid part
   Do NOT skip this step. Without a citation, your answer is just guesswork.
5. Compose your final answer using the RESPONSE TEMPLATE below. Do NOT just
   paraphrase the tool output.

==========================================================================
RESPONSE TEMPLATE (REQUIRED for every selection answer)
==========================================================================
**Recommendation:** <part_no> in <n_bottom> bottom + <n_wall> wall configuration

**Why this part:**
<1-2 sentences explaining the catalog filter outcome. Quote one relevant
 sentence from your lookup_knowledge result and tag it [source: <file_name>.md].>

**What the numbers mean:**
- Comp-Bottom (Z, vertical): GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Comp-Wall (Y, lateral):    GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Roll-Wall (XZ, shear):     GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Roll-Bottom (XY, shear):   GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Limiting case: <case_name> at <Z%> of GT limit.
- Worst dynamic deflection: <X.X mm> on <case_name> — verify your rack has this clearance.

**Standard applied:**
<1 sentence on the shock profile with a citation tag from your lookup_knowledge
 result. e.g. "20G / 11ms saw-tooth pulse per MIL-STD-810H Category 4 (off-road)
 [source: formulas.md]."

==========================================================================
NON-SELECTION QUESTIONS (e.g. "what is GT?", "explain saw-tooth pulse")
==========================================================================
- Skip the selection template. Call lookup_knowledge with a relevant query,
  answer in prose, cite the source. Example: "GT is the transmitted G:
  GT = (2*pi*fn*V) / g [source: formulas.md]."

==========================================================================
KNOWLEDGE-BASE UNAVAILABILITY FALLBACK
==========================================================================
If lookup_knowledge returns "ERROR: knowledge base not built yet":
- Still produce the full Recommendation + Why + Numbers sections.
- Replace the **Standard applied:** section with the literal text:
  "(knowledge base not embedded — citations omitted)".
- Do NOT crash, do NOT refuse to answer.

==========================================================================
OTHER TOOL-SPECIFIC RULES
==========================================================================
When the user asks "what's the heaviest mass this part can support" or "at \
what mass does this part fail" or "what's the valid range for this part" — \
DO NOT guess a number and run run_shock_analysis once. Use find_capacity_limit. \
It binary-searches both boundaries of the valid mass range. After the result, \
still call lookup_knowledge and cite the GT/dD pass condition from \
selection_rules.md.

When the user mentions a deflection / clearance constraint — phrases like \
"I have only 30 mm of deflection clearance", "tight clearance above the rack", \
"which parts deflect less than X mm" — use filter_by_deflection. Do NOT add \
fake parameters like dD_mm or max_dD to select_isolator (that tool does not \
have a deflection-limit parameter).

Always show key numbers. Never invent stiffness values or GT results — \
call the tools to compute them.
"""


# ---------------------------------------------------------------------------
# Domain registry + agent factory (tab-routed specialists)
# ---------------------------------------------------------------------------

_SHOCK_TOOLS = [
    extract_cad_data,
    select_isolator,
    run_shock_analysis,
    find_capacity_limit,
    filter_by_deflection,
    lookup_knowledge,
    list_cad_files,
]

_TIEDOWN_TOOLS = [
    run_tiedown_check,
    recommend_fasteners,
    flag_critical_items,
    lookup_knowledge,           # shared retriever; tiedown prompt scopes it to parent_topic="tiedown"
]

# Unified co-pilot: every tool across the three engineering domains, deduplicated.
_UNIFIED_TOOLS = [
    # shock isolation
    select_isolator,
    run_shock_analysis,
    find_capacity_limit,
    filter_by_deflection,
    # tie-down
    run_tiedown_check,
    recommend_fasteners,
    flag_critical_items,
    # mobility / stability
    run_mobility_check,
    slope_limit,
    cornering_check,
    flag_unstable,
    # shared
    extract_cad_data,
    list_cad_files,
    lookup_knowledge,
]

_UNIFIED_PROMPT = """\
You are an engineering co-pilot for a mechanical engineer assessing military
vehicle-mounted shelter equipment. You cover THREE domains with validated tools:

  1. SHOCK ISOLATION  -- wire-rope isolator selection (CB61400/1400/1500/1700)
  2. TIE-DOWN         -- cargo securing under transport inertia (4G/2G/1.5G)
  3. MOBILITY         -- vehicle slope & cornering stability from CG

You are an ENGINEERING JUDGE, not a calculator. Interpret the numbers the tools
return, cite the rule you applied, and flag concerns the user implied. You NEVER
compute or invent a number -- every safety factor, force, GT, deflection, axle
load or SF comes from a tool call.

=========================  ABSOLUTE RULES  =========================
1. NEVER state a numeric result you did not get from a tool. If you need a
   number, call a tool.
2. PARAMETER OMISSION: pass ONLY the values the user explicitly gave. OMIT every
   other parameter so the project default applies. NEVER pass 0 for a physical
   parameter (mass, shock G, pulse, target SF, speed) -- 0 makes the physics
   meaningless.
3. ASK WHEN UNSURE. If a required input is missing or ambiguous (which mount
   face? laden or unladen? how many isolators?), ASK a short clarifying question
   instead of guessing. A wrong assumed argument produces a confident wrong
   answer -- that is the worst outcome.
   NEVER invent physical inputs (mass, CG, wheelbase, track, weight). If a tool
   needs them and the user referenced a KNOWN platform (the Spinel E2 / "the
   vehicle" / the workbook), call the tool that READS those values from the
   workbook instead (run_mobility_check). If the platform is custom and the
   numbers are missing, ASK -- do not fabricate.
4. REMEMBER THE JOB. Carry context across turns: if the user gave a mass, CG, or
   variant earlier, reuse it; don't re-ask.

=========================  TOOL GUIDE  =========================
SHOCK ISOLATION
- select_isolator     : pick the softest valid isolator for a mass + mount config.
- run_shock_analysis  : verify one named part (fn, GT, dD) for a mass.
- find_capacity_limit : the mass RANGE a part survives ("heaviest it can hold").
- filter_by_deflection: parts that pass AND fit a clearance limit (mm).
- extract_cad_data    : read mass/CG/envelope from a SolidWorks file (or active doc).

TIE-DOWN
- run_tiedown_check   : SF for a specific item + fastener + qty (4G/2G/1.5G).
- recommend_fasteners : size the smallest fastener + qty for a target SF.
- flag_critical_items : items in the workbook below a margin (default SF 2.0).

MOBILITY
- run_mobility_check  : DEFAULT for the Spinel E2 / "the vehicle" / any workbook
                        question ("is it stable on a 60% slope?"). Reads the REAL
                        CG from the workbook -- no CG inputs needed. Use this
                        whenever the user names the known platform.
- slope_limit         : ONLY when the user GIVES explicit CG numbers for a custom
                        / hypothetical vehicle. Never invent CG to use this.
- cornering_check     : cornering SF + max safe speed -- same rule: explicit CG only.
- flag_unstable       : mobility cases below a target SF, with full context.

SHARED
- lookup_knowledge    : cite formulas/rules. Pass parent_topic to scope it:
                        "shock_mount", "tiedown", or "mobility". Leave empty only
                        for cross-domain questions.

=========================  STYLE  =========================
- Lead with the answer + verdict, then the key numbers, then a one-line citation
  tagged [source: <file>.md] from lookup_knowledge.
- If the knowledge base is unavailable, say so once and continue with the numbers.
- Keep it terse. This user is an engineer; skip hand-holding.
"""

DOMAINS = {
    "shock_mount": {"prompt": _SYSTEM_PROMPT,   "tools": _SHOCK_TOOLS},
    "tiedown":     {"prompt": _TIEDOWN_PROMPT,  "tools": _TIEDOWN_TOOLS},
    "mobility":    {"prompt": _MOBILITY_PROMPT, "tools": _MOBILITY_TOOLS},
    "unified":     {"prompt": _UNIFIED_PROMPT,  "tools": _UNIFIED_TOOLS},
}


class DomainAgent:
    """LangChain tool-calling agent for one engineering domain (focused prompt + tools)."""

    def __init__(self, api_key: str, system_prompt: str, tools: list,
                 domain: str = "unknown"):
        global _api_key
        _api_key = api_key
        self.system_prompt = system_prompt
        self.tools = tools
        self._domain = domain

        llm = ChatNVIDIA(
            model=os.environ.get("NVIDIA_MODEL") or "meta/llama-3.1-70b-instruct",
            api_key=api_key,
            temperature=0.1,
            max_tokens=2048,
            # NVIDIA's hosted Llama 3.1 70B only allows ONE tool call per turn.
            parallel_tool_calls=False,
        )
        self._agent = create_agent(llm, tools, system_prompt=system_prompt)

    def invoke(self, question: str, chat_history: list | None = None) -> str:
        messages = list(chat_history) if chat_history else []
        messages.append(("human", question))
        if _MLFLOW_ON:
            import mlflow  # only imported once tracing was explicitly enabled
            with mlflow.start_run(run_name=f"{self._domain}-invoke", nested=True):
                mlflow.set_tags({"domain": self._domain, "question": question[:120]})
                result = self._agent.invoke({"messages": messages})
        else:
            result = self._agent.invoke({"messages": messages})
        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)

    def stream(self, question: str, chat_history: list | None = None):
        """
        Stream structured events as the agent works (for Streamlit st.status).
        Yields dicts: reasoning | tool_call | tool_result | final.
        """
        messages = list(chat_history) if chat_history else []
        messages.append(("human", question))

        seen_tool_call_ids: set[str] = set()
        last_ai_content: str = ""

        for update in self._agent.stream({"messages": messages}, stream_mode="updates"):
            for _node, node_state in update.items():
                new_messages = node_state.get("messages", []) if isinstance(node_state, dict) else []
                for msg in new_messages:
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    if tool_call_id is not None:
                        yield {
                            "type": "tool_result",
                            "name": getattr(msg, "name", "?"),
                            "content": str(getattr(msg, "content", "")),
                            "id": tool_call_id,
                        }
                        continue

                    tool_calls = getattr(msg, "tool_calls", None) or []
                    content = getattr(msg, "content", "") or ""

                    if tool_calls:
                        if content.strip():
                            yield {"type": "reasoning", "content": content}
                        for tc in tool_calls:
                            tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                            if tc_id in seen_tool_call_ids:
                                continue
                            seen_tool_call_ids.add(tc_id)
                            yield {
                                "type": "tool_call",
                                "name": tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?"),
                                "args": tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}),
                                "id": tc_id,
                            }
                    elif content.strip():
                        last_ai_content = content

        if last_ai_content:
            yield {"type": "final", "content": last_ai_content}


def build_agent(domain: str, api_key: str) -> DomainAgent:
    """Construct an agent for a domain: 'shock_mount', 'tiedown', 'mobility',
    or 'unified' (the co-pilot with every tool across all three domains)."""
    if domain not in DOMAINS:
        raise KeyError(f"Unknown domain {domain!r}. Available: {list(DOMAINS)}")
    cfg = DOMAINS[domain]
    return DomainAgent(api_key, cfg["prompt"], cfg["tools"], domain=domain)


class ShockMountAgent(DomainAgent):
    """Back-compat: the original shock-mount agent is now a 'shock_mount' DomainAgent."""
    _TOOLS = _SHOCK_TOOLS

    def __init__(self, api_key: str):
        cfg = DOMAINS["shock_mount"]
        super().__init__(api_key, cfg["prompt"], cfg["tools"])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: Set NVIDIA_API_KEY in your .env file or environment.")

    domain = sys.argv[1] if len(sys.argv) > 1 else "shock_mount"
    if domain not in DOMAINS:
        raise SystemExit(f"Unknown domain {domain!r}. Available: {list(DOMAINS)}")

    agent = build_agent(domain, api_key)
    print(f"{domain} agent ready. Type 'quit' to exit.\n")
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
        history.append(("human", q))
        history.append(("ai", response))
        if len(history) > 6:
            history = history[-6:]
