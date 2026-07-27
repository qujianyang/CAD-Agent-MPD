"""
Agentic shock mount selection assistant.
LangChain tool-calling agent wrapping physics engine, catalog, CAD extractor, and RAG.
LLM: meta/llama-3.1-70b-instruct (NVIDIA API) — supports tool calling.
"""
import json
import os
import re
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

from llm_config import LLMConfig, resolve_llm_config
from physics_engine import ShockEnv, run_analysis, format_report
from catalog import (
    ALL_CATALOGS, AUTO_SELECT_CATALOGS, SELECT_OBJECTIVES,
    CB61400_CATALOG, CB1400_CATALOG, CB1500_CATALOG, CB1700_CATALOG,
    select_and_analyze, format_selection_table, selection_context_for_llm,
)
from custom_isolator import (
    CustomIsolatorInput, DirectionInput, StiffnessInput,
    ValidationError as CustomIsolatorValidationError,
)
from custom_isolator_analysis import analyze_custom_isolator as _analyze_custom_isolator_backend
from cad_compliance_checker import extract_cad_data as _extract_cad_data_raw
from tiedown_tools import (
    run_tiedown_check, recommend_fasteners, get_fastener_data, check_workbook_item,
    _TIEDOWN_PROMPT,
)
from mobility_tools import _MOBILITY_PROMPT, _MOBILITY_TOOLS

# Module-level state — set by ShockMountAgent.__init__ before tools are called
_api_key: Optional[str] = None
_rag: Optional[object] = None
_knowledge_embedder: Optional[object] = None
_knowledge_store: Optional[object] = None

# The normal UI uses the mixed development index. Evaluation can point this at
# a frozen, domain-specific index without altering retrieval code.
KNOWLEDGE_STORE_PATH = os.environ.get(
    "KNOWLEDGE_STORE_PATH", "artifacts/knowledge_embeddings.json"
)
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "nvidia").strip().lower()
try:
    KNOWLEDGE_MAX_CHARS_PER_HIT = max(
        200, int(os.environ.get("KNOWLEDGE_MAX_CHARS_PER_HIT", "1400"))
    )
except ValueError:
    KNOWLEDGE_MAX_CHARS_PER_HIT = 1400


def _truncate_knowledge_content(content: str) -> str:
    """Keep RAG tool output within the LLM's fixed context budget."""
    if len(content) <= KNOWLEDGE_MAX_CHARS_PER_HIT:
        return content
    return (
        f"{content[:KNOWLEDGE_MAX_CHARS_PER_HIT].rstrip()}\n\n"
        "[Excerpt truncated to preserve context for the answer.]"
    )


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
        from nvidia_embedder import NVIDIAEmbedder, OllamaEmbedder, JSONVectorStore
        if not Path(KNOWLEDGE_STORE_PATH).exists():
            return None, None
        if EMBEDDING_PROVIDER == "ollama":
            _knowledge_embedder = OllamaEmbedder(
                model=os.environ.get("OLLAMA_EMBEDDING_MODEL", "bge-m3"),
                base_url=os.environ.get("OLLAMA_EMBEDDING_BASE_URL", "http://127.0.0.1:11434"),
            )
        elif EMBEDDING_PROVIDER == "nvidia":
            _knowledge_embedder = NVIDIAEmbedder(_api_key) if _api_key else None
        else:
            raise ValueError(
                f"Unsupported EMBEDDING_PROVIDER={EMBEDDING_PROVIDER!r}; use 'nvidia' or 'ollama'."
            )
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


def _parse_pulse_shape(pulse_shape: str):
    """Normalize a pulse-shape string; fall back to sawtooth with a NOTE."""
    s = (pulse_shape or "").strip().lower().replace("-", "_").replace(" ", "_")
    if s in ("", "sawtooth", "saw_tooth"):
        return "sawtooth", None
    if s in ("half_sine", "halfsine"):
        return "half_sine", None
    return "sawtooth", (f"pulse_shape was {pulse_shape!r} (unknown); substituted "
                        f"default 'sawtooth' (valid: sawtooth, half_sine)")


@tool
def select_isolator(
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    series: str = "AUTO",
    pulse_shape: str = "sawtooth",
    objective: str = "max_clearance",
) -> str:
    """
    Select the optimal wire rope isolator. By DEFAULT scans the practical-rack range
    CB1400 / CB1500 / CB1700; the softer 6-strand CB61400 is opt-in (pass series="ALL").
    Evaluates every matching part and recommends the best per `objective` (default:
    STIFFEST that passes = least movement / max clearance):
      - GT < GT_limit in all 3 load directions (compression vertical, lateral, shear)
      - Dynamic deflection < isolator's rated travel in all 3 directions
    Returns the full selection table plus mathematical proof for the recommended part.

    IMPORTANT — parameter handling:
    Only pass values for parameters the user explicitly specifies. For everything
    else, OMIT the parameter so the project default applies. Do NOT guess and do
    NOT pass 0 for the shock parameters — 0 makes the physics trivial.

    Project defaults (used if you omit the parameter):
        n_bottom=6, n_wall=4, Ao_G=20.0G, to_ms=11.0 (11 ms),
        GT_limit_G=10.0G, series="AUTO", pulse_shape="sawtooth",
        objective="max_clearance"

    Args:
        mass_kg    : REQUIRED. Total assembly mass in kg. Get from extract_cad_data
                     or ask the user.
        n_bottom   : Number of bottom-mounted isolators. Default 6. OMIT unless user says.
        n_wall     : Number of wall-mounted isolators. Default 4. OMIT unless user says.
        Ao_G       : Shock magnitude in G. Default 20.0 (MIL-STD-810H Category 4).
                     OMIT unless user explicitly gives a different shock spec.
        to_ms      : Shock pulse duration in MILLISECONDS. Default 11.0 (11 ms saw-tooth).
                     OMIT unless user explicitly gives a different pulse duration.
        GT_limit_G : Max allowable transmitted G. Default 10.0 G. OMIT unless user says.
        series     : Catalog filter. Default "AUTO" (CB1400/CB1500/CB1700 — practical
                     19" rack range). Pass "ALL" to also include the softer 6-strand
                     CB61400, or a single series name ("CB61400"/"CB1400"/"CB1500"/"CB1700").
        pulse_shape: "sawtooth" (default) or "half_sine". OMIT unless the user
                     names a pulse shape. Half-sine is ~27% harsher for the same Ao/to.
        objective  : Tiebreak among passing parts: "max_clearance" (smallest
                     deflection, default) or "best_isolation" (softest / lowest
                     transmitted shock). OMIT unless the user states a preference.
    """
    catalog_map = {
        "AUTO":   AUTO_SELECT_CATALOGS,   # default: practical rack range, excludes CB61400
        "CB1400": CB1400_CATALOG,
        "CB1500": CB1500_CATALOG,
        "CB61400": CB61400_CATALOG,
        "CB1700": CB1700_CATALOG,
        "ALL":    ALL_CATALOGS,           # opt-in: adds the softer 6-strand CB61400
    }
    catalog = catalog_map.get(series.upper(), AUTO_SELECT_CATALOGS)

    if mass_kg <= 0:
        return "ERROR: mass_kg must be a positive number. Ask the user for the assembly mass in kg, or call extract_cad_data to read it from SolidWorks."

    # Safety net: the LLM sometimes passes 0 or negative values for shock params
    # (it truncates 0.011 -> "0"). Clamp to defaults and tell everyone what we did.
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted default 20.0 G")
        Ao_G = 20.0
    if to_ms is None or to_ms <= 0:
        substitutions.append(f"to_ms was {to_ms!r} (invalid); substituted default 11.0 ms")
        to_ms = 11.0
    to_s = to_ms / 1000.0
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0
    pulse, pulse_note = _parse_pulse_shape(pulse_shape)
    if pulse_note:
        substitutions.append(pulse_note)
    if objective not in SELECT_OBJECTIVES:
        substitutions.append(f"objective was {objective!r} (unknown); substituted default "
                             f"'max_clearance' (valid: {', '.join(SELECT_OBJECTIVES)})")
        objective = "max_clearance"

    env = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G, pulse_shape=pulse)

    report, candidates = select_and_analyze(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        cad_props=None,     # CG coordinate calibration pending; mass-only for now
        shock_env=env,
        catalog=catalog,
        objective=objective,
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
        f"Input:  mass={mass_kg} kg | mounts={n_bottom} bottom + {n_wall} wall | "
        f"shock={Ao_G}G/{to_s*1000:.0f}ms {pulse} | GT_limit={GT_limit_G}G | objective={objective}",
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
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    pulse_shape: str = "sawtooth",
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
        n_bottom=6, n_wall=4, Ao_G=20.0G, to_ms=11.0 (11 ms), GT_limit_G=10.0G

    Args:
        mass_kg    : REQUIRED. Total assembly mass in kg.
        part_no    : REQUIRED. Isolator part number, e.g. 'CB1400-15', 'CB1500-30'.
        n_bottom   : Bottom-mount count. Default 6. OMIT unless user says.
        n_wall     : Wall-mount count.   Default 4. OMIT unless user says.
        Ao_G       : Shock magnitude in G. Default 20.0. OMIT unless user specifies.
        to_ms      : Shock pulse duration in MILLISECONDS. Default 11.0. OMIT unless user specifies.
        GT_limit_G : Max allowable transmitted G. Default 10.0. OMIT unless user says.
        pulse_shape: "sawtooth" (default) or "half_sine". OMIT unless the user
                     names a pulse shape. Half-sine is ~27% harsher for the same Ao/to.
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
    if to_ms is None or to_ms <= 0:
        substitutions.append(f"to_ms was {to_ms!r} (invalid); substituted default 11.0 ms")
        to_ms = 11.0
    to_s = to_ms / 1000.0
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0
    pulse, pulse_note = _parse_pulse_shape(pulse_shape)
    if pulse_note:
        substitutions.append(pulse_note)

    spec = entry.to_isolator_spec()
    env  = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G, pulse_shape=pulse)
    report = run_analysis(mass_kg, n_bottom, n_wall, shock_env=env, isolator=spec)
    body = format_report(report)
    if substitutions:
        note = "NOTE: Tool received invalid shock parameter(s). Substituted defaults:\n"
        for s in substitutions:
            note += f"  - {s}\n"
        return note + "\n" + body
    return body


def _custom_stiffness_from_tool(
    label: str,
    mode: str,
    value: float,
    unit: str,
    frequency_hz: float = 0.0,
    deflection: float = 0.0,
    deflection_unit: str = "",
) -> StiffnessInput:
    """Build one stiffness input from flat LLM-tool arguments."""
    m = (mode or "").strip().lower()
    if m == "direct_k":
        return StiffnessInput.direct_k(value, unit)
    if m == "rated_load_frequency":
        return StiffnessInput.rated_load_frequency(value, unit, frequency_hz)
    if m == "force_deflection":
        return StiffnessInput.force_deflection(value, unit, deflection, deflection_unit)
    raise CustomIsolatorValidationError(
        f"{label}_stiffness_mode must be one of: direct_k, rated_load_frequency, force_deflection"
    )


def _custom_direction_from_tool(
    label: str,
    stiffness_mode: str,
    value: float,
    unit: str,
    max_dynamic_travel: float,
    travel_unit: str,
    frequency_hz: float = 0.0,
    deflection: float = 0.0,
    deflection_unit: str = "",
) -> DirectionInput:
    stiffness = _custom_stiffness_from_tool(
        label,
        stiffness_mode,
        value,
        unit,
        frequency_hz=frequency_hz,
        deflection=deflection,
        deflection_unit=deflection_unit,
    )
    return DirectionInput(
        stiffness=stiffness,
        max_dynamic_travel=max_dynamic_travel,
        travel_unit=travel_unit,
    )


def _format_custom_case(label: str, direction) -> str:
    return (
        f"  {label:<12}: fn={direction.fn_Hz:.2f} Hz | "
        f"GT={direction.GT_G:.3f}/{direction.GT_limit:.1f} G | "
        f"dD={direction.delta_mm:.1f}/{direction.delta_limit_mm:.1f} mm -> "
        f"{'PASS' if direction.passed else 'FAIL'}"
    )


@tool
def analyze_custom_isolator(
    mass_kg: float,
    vendor: str,
    part_no: str,
    comp_stiffness_mode: str,
    comp_value: float,
    comp_unit: str,
    comp_max_dynamic_travel: float,
    comp_travel_unit: str = "mm",
    shear_stiffness_mode: str = "",
    shear_value: float = 0.0,
    shear_unit: str = "",
    shear_max_dynamic_travel: float = 0.0,
    shear_travel_unit: str = "mm",
    comp_frequency_hz: float = 0.0,
    shear_frequency_hz: float = 0.0,
    comp_deflection: float = 0.0,
    comp_deflection_unit: str = "",
    shear_deflection: float = 0.0,
    shear_deflection_unit: str = "",
    max_static_comp: float = 0.0,
    max_static_comp_unit: str = "",
    source: str = "",
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    pulse_shape: str = "sawtooth",
) -> str:
    """
    Analyze a non-catalog/custom wire-rope isolator using vendor-supplied data.

    Use this when the part is NOT in the built-in CB catalog, or when the user
    supplies a vendor row from Vibratec, Socitec, or another manufacturer.
    Python validates units, derives stiffness when needed, runs the existing
    4-case shock engine, and returns the provenance caveat.

    IMPORTANT -- parameter handling:
    Only pass values the user explicitly specifies or that were explicitly
    extracted from a vendor row. OMIT all other parameters so defaults apply.
    Do NOT invent compression/shear data. If shear data is missing, call this
    tool only if you want it to return an error asking for shear data.

    Stiffness modes:
      - direct_k: value is stiffness. Units: N/m, N/mm, lb/in.
      - rated_load_frequency: value is rated load mass, unit kg, plus frequency_hz.
        Example: Vibratec "30 kg at 10 Hz".
      - force_deflection: value is force, units N/daN/kN, plus deflection and
        deflection_unit. Example: Socitec "Max Shock F daN" with "d mm".

    Args:
        mass_kg: REQUIRED. Total supported mass in kg.
        vendor: REQUIRED. Vendor name, e.g. "Vibratec" or "Socitec".
        part_no: REQUIRED. Vendor part number.
        comp_stiffness_mode: REQUIRED. direct_k, rated_load_frequency, or force_deflection.
        comp_value: REQUIRED. Compression K, rated load, or force depending on mode.
        comp_unit: REQUIRED. Unit for comp_value.
        comp_max_dynamic_travel: REQUIRED. Compression max dynamic travel.
        comp_travel_unit: Unit for compression travel. Default mm. OMIT if mm.
        shear_stiffness_mode: REQUIRED. Same modes as compression; do not guess.
        shear_value: REQUIRED. Shear K, rated load, or force depending on mode.
        shear_unit: REQUIRED. Unit for shear_value.
        shear_max_dynamic_travel: REQUIRED. Shear max dynamic travel.
        shear_travel_unit: Unit for shear travel. Default mm. OMIT if mm.
        comp_frequency_hz: REQUIRED only for comp_stiffness_mode=rated_load_frequency.
        shear_frequency_hz: REQUIRED only for shear_stiffness_mode=rated_load_frequency.
        comp_deflection: REQUIRED only for comp_stiffness_mode=force_deflection.
        comp_deflection_unit: REQUIRED only for comp_stiffness_mode=force_deflection.
        shear_deflection: REQUIRED only for shear_stiffness_mode=force_deflection.
        shear_deflection_unit: REQUIRED only for shear_stiffness_mode=force_deflection.
        max_static_comp: Optional vendor max static compression load. OMIT if absent.
        max_static_comp_unit: Unit for max_static_comp: kg, daN, or N. OMIT if absent.
        source: Optional short provenance note. OMIT unless known.
        n_bottom: Bottom mount count. Default 6. OMIT unless user says.
        n_wall: Wall mount count. Default 4. OMIT unless user says.
        Ao_G: Shock magnitude in G. Default 20.0. OMIT unless user specifies.
        to_ms: Shock pulse duration in milliseconds. Default 11.0. OMIT unless user specifies.
        GT_limit_G: Max allowable transmitted G. Default 10.0. OMIT unless user says.
        pulse_shape: sawtooth (default) or half_sine. OMIT unless user specifies.
    """
    substitutions: list[str] = []
    if Ao_G is None or Ao_G <= 0:
        substitutions.append(f"Ao_G was {Ao_G!r} (invalid); substituted default 20.0 G")
        Ao_G = 20.0
    if to_ms is None or to_ms <= 0:
        substitutions.append(f"to_ms was {to_ms!r} (invalid); substituted default 11.0 ms")
        to_ms = 11.0
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0
    pulse, pulse_note = _parse_pulse_shape(pulse_shape)
    if pulse_note:
        substitutions.append(pulse_note)

    try:
        raw = CustomIsolatorInput(
            vendor=vendor,
            part_no=part_no,
            compression=_custom_direction_from_tool(
                "comp",
                comp_stiffness_mode,
                comp_value,
                comp_unit,
                comp_max_dynamic_travel,
                comp_travel_unit,
                frequency_hz=comp_frequency_hz,
                deflection=comp_deflection,
                deflection_unit=comp_deflection_unit,
            ),
            shear=_custom_direction_from_tool(
                "shear",
                shear_stiffness_mode,
                shear_value,
                shear_unit,
                shear_max_dynamic_travel,
                shear_travel_unit,
                frequency_hz=shear_frequency_hz,
                deflection=shear_deflection,
                deflection_unit=shear_deflection_unit,
            ),
            max_static_comp=max_static_comp if max_static_comp > 0 else None,
            max_static_comp_unit=max_static_comp_unit if max_static_comp > 0 else None,
            source=source,
        )
        env = ShockEnv(
            Ao_G=Ao_G,
            to_s=to_ms / 1000.0,
            GT_limit_G=GT_limit_G,
            pulse_shape=pulse,
        )
        result = _analyze_custom_isolator_backend(
            raw,
            mass_kg=mass_kg,
            n_bottom=n_bottom,
            n_wall=n_wall,
            shock_env=env,
        )
    except CustomIsolatorValidationError as exc:
        return f"ERROR: {exc}"

    dirs = result.report.directions
    static_text = "not published"
    if result.static_rating_daN is not None:
        static_text = (
            f"{result.static_load_daN:.1f} / {result.static_rating_daN:.1f} daN per bottom mount "
            f"-> {'PASS' if result.static_ok else 'FAIL'}"
        )

    lines: list[str] = []
    if substitutions:
        lines.append("NOTE: Tool received invalid shock parameter(s). Substituted defaults:")
        for s in substitutions:
            lines.append(f"  - {s}")
        lines.append("")
    lines += [
        "=== CUSTOM ISOLATOR ANALYSIS ===",
        f"Part: {result.normalized.spec.name}",
        f"Source: {result.normalized.source or '(user/vendor data)'}",
        f"Verdict: {result.verdict}",
        f"Validation: {result.validation_level}",
        f"Stiffness source: comp={result.normalized.stiffness_source_comp}, "
        f"shear={result.normalized.stiffness_source_shear}",
        f"Config: mass={mass_kg} kg | mounts={n_bottom} bottom + {n_wall} wall | "
        f"shock={Ao_G}G/{to_ms:.0f}ms {pulse} | GT_limit={GT_limit_G}G",
        f"Static load: {static_text}",
        "",
        "4 load cases:",
        _format_custom_case("Comp-Bottom", dirs[0]),
        _format_custom_case("Comp-Wall", dirs[1]),
        _format_custom_case("Roll-Wall", dirs[2]),
        _format_custom_case("Roll-Bottom", dirs[3]),
    ]
    if result.warnings:
        lines.append("")
        lines.append("Warnings / caveats:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


@tool
def lookup_knowledge(query: str, parent_topic: str = "") -> str:
    """
    Search the hierarchical engineering knowledge base (knowledge/ folder).

    Primary parent topic: 'shock_mount' — focused reference chunks covering:
      - formulas: impulse_velocity, natural_frequency, transmitted_acceleration,
        dynamic_deflection; load_distribution and four_load_cases
      - gates and decisions: static_load_gate, travel_limit_gate,
        governing_check, missing_input_policy
      - workflows and objectives: selection_workflow, verification_workflow,
        max_clearance_objective (DEFAULT: stiffest passing part, smallest
        deflection), best_isolation_objective (softest passing part, lowest GT)
      - catalogue provenance: cb1400_catalog, cb1500_catalog, cb1700_catalog,
        cb61400_optional_scope
      - standard basis: project_shock_requirements (where 20G/11ms/10G come
        from), standard_scope, pulse_sawtooth, pulse_half_sine, and six
        mil_std_516_8_* method pages
      - model scope: model_assumptions, model_limitations,
        road_vibration_check, installation_considerations,
        validation_excel_baseline
      - supplied vendor evidence: vendor_source_register,
        socitec_cb1390_construction, socitec_cb1390_performance,
        vendor_cb1390_hh14_cases, vendor_cb1400_cases,
        vendor_nonlinear_model_boundary,
        vendor_effective_configuration_count, shock_vibration_separation
      - implementation workflow: installation_acceptance_workflow and
        supplier_data_requirements

    Use this to cite formulas, justify defaults and objectives, quote catalogue
    provenance, or explain standard basis and model limits. Numerical results
    always come from the deterministic tools, never from these pages.

    Args:
        query:         What you want to know, in natural language.
                       Examples: "GT formula", "why divide mass by 2",
                       "where does 20 G come from", "CB61400 static rating".
        parent_topic:  Optional filter — e.g. "shock_mount". Leave empty to
                       search across all topics.

    Returns the top matching pages with topic labels so they can be cited.
    """
    embedder, store = _get_knowledge_search()
    if store is None:
        return ("ERROR: knowledge base not built yet. Run `python setup_knowledge.py` "
                "to ingest the knowledge/ folder.")
    if embedder is None:
        return "ERROR: embedding provider is not configured; cannot embed query."

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
            f"{_truncate_knowledge_content(h['content'])}\n"
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
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    pulse_shape: str = "sawtooth",
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
        to_ms     : Shock pulse duration in MILLISECONDS. Default 11.0. OMIT unless user specifies.
        GT_limit_G: Max allowable transmitted G. Default 10.0. OMIT unless user specifies.
        pulse_shape: "sawtooth" (default) or "half_sine". OMIT unless the user
                     names a pulse shape.

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
    if to_ms is None or to_ms <= 0:
        substitutions.append(f"to_ms was {to_ms!r} (invalid); substituted default 11.0 ms")
        to_ms = 11.0
    to_s = to_ms / 1000.0
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted default 10.0 G")
        GT_limit_G = 10.0
    pulse, pulse_note = _parse_pulse_shape(pulse_shape)
    if pulse_note:
        substitutions.append(pulse_note)

    spec = entry.to_isolator_spec()
    env  = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G, pulse_shape=pulse)

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
            f"Config: {n_bottom} bottom + {n_wall} wall mounts | Shock: {Ao_G}G/{to_s*1000:.0f}ms {pulse} | GT limit: {GT_limit_G}G\n\n"
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
        f"Shock : {Ao_G}G / {to_s*1000:.0f}ms {pulse}",
        f"GT limit: {GT_limit_G}G | Travel limits: dmax_comp={entry.d_max_comp_mm:.1f}mm, dmax_shear={entry.d_max_shear_mm:.1f}mm",
        "",
        f"Valid mass range: {M_min:.0f} kg <= M <= {M_max:.0f} kg",
        "",
        f"  LOWER bound = {M_min:.0f} kg",
        f"    Below this, part FAILS: {M_min_reason}",
        f"  UPPER bound = {M_max:.0f} kg",
        f"    Above this, part FAILS: {M_max_reason}",
    ]

    # Impulse-approximation validity at the lower bound: at small masses fn is
    # high and the velocity-shock formula (fn*t0 <= 0.25) stops being valid —
    # flag so the bound is read as indicative, not exact.
    _, r_at_min = _eval(max(M_min, SEARCH_LO))
    if r_at_min and any(not d.impulse_valid for d in r_at_min.directions):
        lines += [
            "",
            "NOTE: at the LOWER bound the impulse approximation (fn*t0 <= 0.25) is "
            "no longer valid — treat the lower limit as indicative only.",
        ]
    return "\n".join(lines)


@tool
def filter_by_deflection(
    mass_kg: float,
    max_dD_mm: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    series: str = "AUTO",
    pulse_shape: str = "sawtooth",
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
        to_ms      : Shock pulse duration in MILLISECONDS. Default 11.0. OMIT unless user says.
        GT_limit_G : Maximum transmitted G. Default 10.0. OMIT unless user says.
        series     : Catalog filter. Default "AUTO" (CB1400/CB1500/CB1700 — practical
                     19" rack range). Pass "ALL" to also include the softer 6-strand
                     CB61400, or a single series name.
        pulse_shape: "sawtooth" (default) or "half_sine". OMIT unless the user
                     names a pulse shape.

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
    if to_ms is None or to_ms <= 0:
        substitutions.append(f"to_ms was {to_ms!r} (invalid); substituted 11.0 ms")
        to_ms = 11.0
    to_s = to_ms / 1000.0
    if GT_limit_G is None or GT_limit_G <= 0:
        substitutions.append(f"GT_limit_G was {GT_limit_G!r} (invalid); substituted 10.0 G")
        GT_limit_G = 10.0
    pulse, pulse_note = _parse_pulse_shape(pulse_shape)
    if pulse_note:
        substitutions.append(pulse_note)

    catalog_map = {
        "AUTO":   AUTO_SELECT_CATALOGS,   # default: practical rack range, excludes CB61400
        "CB1400": CB1400_CATALOG,
        "CB1500": CB1500_CATALOG,
        "CB61400": CB61400_CATALOG,
        "CB1700": CB1700_CATALOG,
        "ALL":    ALL_CATALOGS,           # opt-in: adds the softer 6-strand CB61400
    }
    catalog = catalog_map.get(series.upper(), AUTO_SELECT_CATALOGS)
    env = ShockEnv(Ao_G=Ao_G, to_s=to_s, GT_limit_G=GT_limit_G, pulse_shape=pulse)

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
        f"shock={Ao_G}G/{to_s*1000:.0f}ms {pulse} | GT_limit={GT_limit_G}G",
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


_SERIES_MAP = {
    "CB61400": CB61400_CATALOG,
    "CB1400":  CB1400_CATALOG,
    "CB1500":  CB1500_CATALOG,
    "CB1700":  CB1700_CATALOG,
}


@tool
def get_isolator_data(part_no: str = "", series: str = "") -> str:
    """
    DATA LOOKUP in the isolator catalog -- no analysis. Use this for:
      - "what is the stiffness / rated travel / size of CB1400-30?"
      - "what parts are in the CB1500 series?"
      - "what series / parts are available?"
    Catalog numbers come from THIS tool only -- never from memory, and never
    convert lb/in to N/m yourself.

    OMIT both arguments for the overview of all four series.

    Args:
        part_no : Exact part number, e.g. "CB1400-30". OMIT if asking about a series.
        series  : "CB61400", "CB1400", "CB1500" or "CB1700". OMIT for all series.
    """
    if part_no.strip():
        key = part_no.strip().upper()
        entry = next((e for e in ALL_CATALOGS if e.part_no.upper() == key), None)
        if entry is None:
            available = sorted({e.part_no for e in ALL_CATALOGS})
            return (f"ERROR: Part '{part_no}' not found in catalog.\n"
                    f"Available parts: {', '.join(available)}")
        return "\n".join([
            f"Part: {entry.part_no}  (Series {entry.series})",
            f"  Size (H x W)        : {entry.H_in}\" x {entry.W_in}\"  "
            f"({entry.H_in * 25.4:.1f} x {entry.W_in * 25.4:.1f} mm)",
            f"  K compression       : {entry.k_comp_lbin:,.0f} lb/in  ({entry.k_comp_Nm:,.0f} N/m)",
            f"  K shear/roll        : {entry.k_shear_lbin:,.0f} lb/in  ({entry.k_shear_Nm:,.0f} N/m)",
            f"  Rated travel (comp) : {entry.d_max_comp_in}\"  ({entry.d_max_comp_mm:.2f} mm)",
            f"  Rated travel (shear): {entry.d_max_shear_in}\"  ({entry.d_max_shear_mm:.2f} mm)",
        ])

    if series.strip():
        key = series.strip().upper()
        cat = _SERIES_MAP.get(key)
        if cat is None:
            return (f"ERROR: unknown series {series!r}. "
                    f"Valid series: {', '.join(_SERIES_MAP)}.")
        lines = [
            f"=== {key} SERIES ({len(cat)} parts; softest last) ===",
            f"{'Part':<12} {'Kcomp lb/in':>12} {'Kshear lb/in':>13} "
            f"{'dmax comp mm':>13} {'dmax shear mm':>14}",
        ]
        for e in sorted(cat, key=lambda e: -e.k_comp_lbin):
            lines.append(f"{e.part_no:<12} {e.k_comp_lbin:>12,.0f} {e.k_shear_lbin:>13,.0f} "
                         f"{e.d_max_comp_mm:>13.2f} {e.d_max_shear_mm:>14.2f}")
        return "\n".join(lines)

    lines = ["=== ISOLATOR CATALOG OVERVIEW (4 series) ===",
             "Stiffer K -> higher GT but less deflection; softer K -> better isolation."]
    for name, cat in _SERIES_MAP.items():
        ks = [e.k_comp_lbin for e in cat]
        ds = [e.d_max_comp_mm for e in cat]
        lines.append(
            f"  {name:<8} {len(cat):>2} parts | K_comp {min(ks):,.0f}-{max(ks):,.0f} lb/in | "
            f"rated travel {min(ds):.0f}-{max(ds):.0f} mm"
        )
    lines.append("Note: CB61400 (6-strand) is in the catalog but EXCLUDED from default "
                 "auto-selection — it is too soft (large deflection) for standard racks. "
                 "It is selected only on explicit opt-in.")
    lines.append("Give a series for its full table, or a part number for exact data.")
    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a mechanical engineering design assistant specializing in shock isolation \
for military vehicle-mounted shelter equipment.

You act as an ENGINEERING JUDGE, not a tool dispatcher. Your job is to interpret \
the numbers the tools give you, cite the engineering rule you applied, and actively \
flag concerns the user implied but did not state. Do NOT just paraphrase the tool output.

NON-NEGOTIABLE — NEVER answer from memory. You may not state a part number, GT \
value, stiffness, deflection, pass/fail verdict, or formula unless it came from a \
tool call in THIS turn. Tool results from earlier turns do NOT count — a new \
question needs a new tool call, even if it looks similar to one already answered. \
If you are about to write a recommendation or verdict without having called a tool \
this turn, STOP and call the tool first.

Your primary task: select or verify wire rope isolators for equipment racks given \
mass, mount configuration, and shock environment. Built-in catalog selection covers \
CB61400, CB1400, CB1500, and CB1700. For non-catalog vendor rows such as Vibratec, \
Socitec, or custom parts, use analyze_custom_isolator.

Standard defaults (used automatically if you omit the parameter — see CRITICAL rule below):
- Shock profile : 20G, 11ms saw-tooth (MIL-STD-810H Category 4 off-road)
- GT limit      : 10G transmitted
- Mount config  : 6 bottom + 4 wall isolators (typical 4-bay rack)

CRITICAL — parameter passing rule for ALL tools:
- Only pass values for parameters the user EXPLICITLY mentions.
- For every other parameter, OMIT it from the tool call so the project default applies.
- Never pass 0 or "0" for shock parameters (Ao_G, to_ms, GT_limit_G). Passing 0
  makes the physics trivial and the result meaningless.
- Pulse duration is to_ms in MILLISECONDS (e.g. an 11 ms pulse is to_ms=11), NOT seconds.
- Numeric parameters: pass real numbers (e.g. to_ms=11, Ao_G=20.0), never strings of
  truncated numbers (e.g. "0" instead of 11).

PULSE SHAPE: every analysis tool accepts pulse_shape ("sawtooth" default, or
"half_sine"). Pass "half_sine" ONLY when the user says half-sine; otherwise OMIT
it. A half-sine pulse is ~27% harsher for the same Ao/to (V = (2/pi)*g*Ao*to vs
0.5*g*Ao*to) — NEVER answer a half-sine question with sawtooth numbers.

DEFAULT SELECTION scans CB1400/CB1500/CB1700 (the practical 19" rack range). The
softer 6-strand CB61400 is OPT-IN: it produces large deflections at typical rack
masses, so OMIT series (default "AUTO") for normal requests and NEVER recommend a
CB61400 part by default. Only pass series="ALL" (or series="CB61400") when the user
explicitly asks for CB61400 or for the maximum-softness option.

CATALOG NUMBERS (stiffness K, rated travel dmax, part size) come ONLY from
get_isolator_data — never from memory, and never convert lb/in to N/m yourself.

==========================================================================
WORKFLOW FOR ISOLATOR SELECTION QUESTIONS
==========================================================================
1. Confirm the assembly mass. If the user did not give it, ASK for it.
2. Confirm mount configuration only if the user specified one (else omit).
3. Call select_isolator with ONLY the parameters the user gave you.
4. Compose your final answer using the RESPONSE TEMPLATE below. Answer DIRECTLY
   from the tool result -- do NOT call lookup_knowledge for a routine selection
   (each extra tool call is a slow model turn). Interpret the numbers; do NOT
   just paraphrase the tool output.

==========================================================================
RESPONSE TEMPLATE (REQUIRED for every selection answer)
==========================================================================
**Recommendation:** <part_no> in <n_bottom> bottom + <n_wall> wall configuration

**Why this part:**
<1-2 sentences explaining the catalog filter outcome -- the softest part that
 passes all four load cases.>

**What the numbers mean:**
- Comp-Bottom (Z, vertical): GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Comp-Wall (Y, lateral):    GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Roll-Wall (XZ, shear):     GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Roll-Bottom (XY, shear):   GT = X.X G vs limit Y.Y G  ->  Z% utilization (verdict)
- Limiting case: <case_name> at <Z%> of GT limit.
- Worst dynamic deflection: <X.X mm> on <case_name> — verify your rack has this clearance.

**Standard applied:**
<1 sentence on the shock profile. e.g. "20G / 11ms saw-tooth pulse per
 MIL-STD-810H Category 4 (off-road).">

==========================================================================
EXPLANATION / REFERENCE QUESTIONS (e.g. "what is GT?", "explain saw-tooth pulse")
==========================================================================
- This is the ONLY situation that uses lookup_knowledge. Skip the selection
  template, call lookup_knowledge with a relevant query, answer in prose and
  cite the source. Example: "GT is the transmitted G: GT = (2*pi*fn*V) / g
  [source: formulas.md]." If it returns "ERROR: knowledge base not built yet",
  answer from your own explanation and note that citations are unavailable.

==========================================================================
OTHER TOOL-SPECIFIC RULES
==========================================================================
When the user asks for catalog DATA — "what is the stiffness / travel / size \
of part X", "list the CB1500 parts", "what series exist" — use \
get_isolator_data. Do NOT run an analysis just to read off K or dmax.

When the user provides vendor/custom isolator data -- for example Vibratec rated \
load at frequency, Socitec shock force/deflection data, or a hand-typed custom \
part -- use analyze_custom_isolator. Do NOT convert units or derive K yourself. \
If compression or shear data is missing, ask for it or call the tool to surface \
the missing-field error. Treat screening_only results as preliminary.

When the user states a selection PREFERENCE — "least movement", \
"maximum clearance margin", or "smallest deflection" (default) — pass \
objective="max_clearance" to select_isolator. When the user asks for \
"lowest transmitted shock" or "best isolation", pass objective="best_isolation". \
OMIT objective when the user states no preference.

Always show key numbers. Never invent stiffness values or GT results — \
call the tools to compute them.

CONVERSATION: if the user just greets you or makes small talk ("hi", "hello", \
"what can you do"), reply in ONE short friendly sentence and offer 2-3 example \
questions. Do NOT call a tool or ask for parameters, and NEVER mention tools, \
JSON, or any internal format to the user.
"""


# ---------------------------------------------------------------------------
# Domain registry + agent factory (tab-routed specialists)
# ---------------------------------------------------------------------------

# Core demo set (3 tools + shared RAG): one clear intent each -> Select / Verify / Look up.
# Retired from the agent for demo robustness (functions stay defined; the CAD + Shock
# UI tab and the deflection/capacity panels cover these): extract_cad_data,
# list_cad_files, find_capacity_limit, filter_by_deflection. Re-add to this list to
# bring one back into the chat agent.
_SHOCK_TOOLS = [
    select_isolator,         # Select: softest passing part for a mass + mount config
    run_shock_analysis,      # Verify: GT / fn / dD for one named part
    analyze_custom_isolator, # Verify: custom/vendor part from normalized vendor data
    get_isolator_data,       # Look up: catalog stiffness / travel / size
    lookup_knowledge,        # Optional: cite formulas / rules (explanation questions only)
]

# User-facing capability registry for the shock-mount assistant. Curated for end users —
# one row per registered tool so the drift test (test_every_shock_tool_is_documented)
# can assert complete coverage with registered - documented.
SHOCK_CAPABILITIES = [
    {"capability": "Isolator selection",
     "purpose": "Pick the softest passing part from the CB1400/CB1500/CB1700 catalog (CB61400 6-strand is opt-in)",
     "example": "Select the softest passing isolator for a 1,500 kg rack using 6 bottom and 4 wall mounts under a 20G, 11 ms saw-tooth shock with 10G transmitted limit.",
     "tool": "select_isolator"},
    {"capability": "Shock analysis verification",
     "purpose": "Verify GT, natural frequency, and dynamic deflection for a specific part",
     "example": "Verify whether CB1400-12 passes for a 900 kg rack using 6 bottom and 4 wall mounts under a 15G, 11 ms half-sine shock with 10G transmitted limit.",
     "tool": "run_shock_analysis"},
    {"capability": "Custom vendor isolator analysis",
     "purpose": "Analyze a non-catalog isolator from vendor-supplied stiffness, rated-load/frequency, or force/deflection data",
     "example": "Analyze Vibratec A070146-061 using 30 kg at 10 Hz compression, 6 kg at 10 Hz shear, 32 mm compression travel, and 37 mm shear travel for an 850 kg rack.",
     "tool": "analyze_custom_isolator"},
    {"capability": "Catalog data lookup",
     "purpose": "Stiffness, rated travel and size of any part or series, in catalog and SI units",
     "example": "What are the compression stiffness, shear stiffness, rated travel, and physical size of CB1400-30 in catalog and SI units?",
     "tool": "get_isolator_data"},
    {"capability": "Engineering references",
     "purpose": "Explain shock isolation formulas and catalog selection rules",
     "example": "Explain how transmitted G is calculated and why natural frequency affects shock isolation.",
     "tool": "lookup_knowledge"},
]

_TIEDOWN_TOOLS = [
    run_tiedown_check,
    recommend_fasteners,
    get_fastener_data,
    check_workbook_item,
    lookup_knowledge,           # shared retriever; tiedown prompt scopes it to parent_topic="tiedown"
]

# Mobility domain tools + the shared retriever (lookup_knowledge lives in this module,
# so it can't be appended inside mobility_tools.py without a circular import).
_MOBILITY_TOOLS_FULL = [*_MOBILITY_TOOLS, lookup_knowledge]


def _ui_guide_prompt(tab_label: str, topic: str, engineering_panel: str) -> str:
    """Calculation-free, RAG-only UI-guide prompt for one tab. The guide explains how
    to operate the app and redirects engineering questions to the tab's 💬 panel."""
    return f"""\
You are the {tab_label} UI GUIDE for this application. You explain HOW TO OPERATE
the app -- which control to use, what each input means, what a button does, why it is
disabled. You do NOT perform engineering calculations.

HARD RULES:
- NEVER compute or quote a safety factor, transmitted G, deflection, force, axle load,
  or any engineering number for the user's case. If they ask for a calculation, tell
  them to use the "{engineering_panel}" panel, and suggest the exact question to type
  there.
- ALWAYS call lookup_knowledge with parent_topic="{topic}" before answering, and base
  your answer on what it returns. If it returns nothing useful, say so briefly.
- Be concise and practical. Name the on-screen control exactly as labelled.
- If the user just greets you, reply in ONE friendly sentence and offer 2-3 of the
  quick-start choices. Do not mention tools, JSON, or any internal format to the user.
"""


_UI_GUIDE_TOOLS = [lookup_knowledge]

DOMAINS = {
    "shock_mount": {"prompt": _SYSTEM_PROMPT,    "tools": _SHOCK_TOOLS},
    "tiedown":     {"prompt": _TIEDOWN_PROMPT,   "tools": _TIEDOWN_TOOLS},
    "mobility":    {"prompt": _MOBILITY_PROMPT,  "tools": _MOBILITY_TOOLS_FULL},
    "ui_guide_mobility": {
        "prompt": _ui_guide_prompt("MOBILITY TAB", "ui_guide_mobility",
                                   "Ask the mobility assistant"),
        "tools": _UI_GUIDE_TOOLS},
    "ui_guide_shock": {
        "prompt": _ui_guide_prompt("SHOCK ISOLATOR SELECTOR TAB", "ui_guide_shock",
                                   "Ask the shock-isolation assistant"),
        "tools": _UI_GUIDE_TOOLS},
    "ui_guide_tiedown": {
        "prompt": _ui_guide_prompt("TIE-DOWN TAB", "ui_guide_tiedown",
                                   "Ask the tie-down assistant"),
        "tools": _UI_GUIDE_TOOLS},
}


# ---------------------------------------------------------------------------
# Tool-use enforcement
# ---------------------------------------------------------------------------
# create_agent() lets the model answer directly. For these domains every
# technical answer MUST be grounded in a tool call; if a turn skips its tool we
# retry once with a strict correction, and suppress the answer if it still does.
_ENFORCE_TOOLUSE_DOMAINS = {"shock_mount"}

# Stateless domains: each question is answered independently, with NO chat history
# fed to the model. The UI-guide assistants ("how do I use this tab?") don't need
# conversational memory -- dropping history is faster, cleaner, and avoids stale
# context bleeding between unrelated how-to questions. The visible transcript and
# export in the UI are unaffected; only the LLM input is reset each turn.
def _is_stateless(domain: str) -> bool:
    return (domain or "").startswith("ui_guide")

# Engineering assistants (shock/tiedown/mobility) keep only the last few exchanges
# as LLM input -- long chats otherwise grow the prompt and slow every turn. The full
# transcript stays visible/exported in the UI; only the model input is capped.
_MAX_HISTORY_TURNS = 3   # one "turn" = one (human, ai) exchange


def _limit_history(chat_history: list | None,
                   max_turns: int = _MAX_HISTORY_TURNS) -> list | None:
    """Keep only the last `max_turns` exchanges (2*max_turns messages) of chat history.
    None/short histories pass through unchanged. The UI transcript is unaffected."""
    if not chat_history:
        return chat_history
    return chat_history[-2 * max_turns:]

# Small talk / greetings -> a tool-free reply is fine.
_SMALLTALK_RE = re.compile(
    r"^\s*(hi+|hey+|hello|yo|sup|thanks|thank you|thx|good (morning|afternoon)|"
    r"who are you|what (can|do) you|how are you|help)\b", re.IGNORECASE)
# A technical CLAIM the model must not assert without a tool (part no., verdict,
# GT, catalog data, etc.).
_CLAIM_RE = re.compile(
    r"(cb\s?\d|\bgt\b|\bpass(es|ed)?\b|\bfail(s|ed)?\b|utilization|deflection|"
    r"recommend|% of|g vs|stiffness|rated travel|natural frequency)", re.IGNORECASE)
# A genuine request for a missing REQUIRED input.
_INPUT_REQ_RE = re.compile(
    r"(mass|kg|weight|part\s*(number|no)|which part|mount|configuration|"
    r"shock|pulse|half[\s-]?sine|saw[\s-]?tooth)", re.IGNORECASE)
# A clarification can be a polite declarative sentence, not only a question.
# Keep this deliberately narrow so technical claims still require a tool call.
_CLARIFICATION_REQUEST_RE = re.compile(
    r"\b(?:please\s+(?:provide|supply|share|confirm|re-ask)|"
    r"(?:i\s+)?(?:need|require)\s+(?:the\s+)?|"
    r"(?:cannot|can't)\s+(?:select|verify|analyse|analyze|assess)\s+without)\b",
    re.IGNORECASE,
)

_TOOLUSE_CORRECTION = (
    "You answered WITHOUT calling a tool. Every part number, GT value, stiffness, "
    "deflection, pass/fail verdict and formula MUST come from a tool call in THIS "
    "turn. Call exactly one of: select_isolator, run_shock_analysis, "
    "analyze_custom_isolator, get_isolator_data, lookup_knowledge. Do NOT answer from memory or from earlier "
    "turns -- a new question needs a new tool call.")
_TOOLUSE_SAFE_NOTICE = (
    "I can't ground this in a validated tool, so I won't give numbers that might be "
    "wrong. Please re-ask and include the key inputs (e.g. the rack mass, the part "
    "number, or whether the pulse is half-sine).")

_CURRENT_CONTEXT_MARKERS = (
    "current analysis",
    "current result",
    "this analysis",
    "this result",
    "selected isolator",
    "current isolator",
    "current selection",
    "recommended part",
    "why was",
    "closest-to-fail",
    "closest to failing",
    "governing condition",
    "catalog alternatives",
    "nearest catalog",
    "check next",
)


def _build_chat_model(cfg: LLMConfig):
    if not cfg.api_key:
        raise RuntimeError(f"{cfg.api_key_env} is not set.")

    if cfg.provider in ("openai", "ollama"):
        # Ollama exposes an OpenAI-compatible endpoint, so it reuses ChatOpenAI
        # with a base_url pointed at the local server. This keeps a single code
        # path for local (Ollama now / vLLM later) and hosted OpenAI.
        from langchain_openai import ChatOpenAI
        kwargs = dict(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            top_p=cfg.top_p,
            presence_penalty=cfg.presence_penalty,
        )
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        if cfg.seed is not None:
            kwargs["seed"] = cfg.seed
        if cfg.reasoning_effort:
            kwargs["reasoning_effort"] = cfg.reasoning_effort
        return ChatOpenAI(**kwargs)

    if cfg.provider == "nvidia":
        return ChatNVIDIA(
            model=cfg.model,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            top_p=cfg.top_p,
            presence_penalty=cfg.presence_penalty,
            # NVIDIA's hosted Llama 3.1 70B only allows ONE tool call per turn.
            parallel_tool_calls=False,
        )

    raise RuntimeError(f"Unsupported LLM provider: {cfg.provider}")


def _requires_tool(question: str, answer: str) -> bool:
    """True if a (shock-mount) answer must be backed by a tool call.

    False only for (a) small talk, or (b) a genuine clarification that asks for a
    missing required input AND makes no technical claim. A no-tool answer that
    states a part/verdict -- e.g. "CB1500-80 passes. Want the full report?" -- has a
    '?' but matches a claim, so it still returns True.
    """
    if _SMALLTALK_RE.search(question or ""):
        return False
    a = answer or ""
    asks_for_input = bool(_INPUT_REQ_RE.search(a)) and (
        "?" in a or bool(_CLARIFICATION_REQUEST_RE.search(a))
    )
    makes_claim = bool(_CLAIM_RE.search(a))
    if asks_for_input and not makes_claim:
        return False
    return True


def _is_context_grounded_question(question: str) -> bool:
    """True only for questions that describe an already computed UI result."""
    normalized = " ".join((question or "").lower().split())
    return any(marker in normalized for marker in _CURRENT_CONTEXT_MARKERS)


class DomainAgent:
    """LangChain tool-calling agent for one engineering domain (focused prompt + tools)."""

    def __init__(self, api_key: str, system_prompt: str, tools: list,
                 domain: str = "unknown"):
        global _api_key
        cfg = resolve_llm_config()
        if cfg.provider == "nvidia":
            _api_key = cfg.api_key or api_key
        else:
            _api_key = (os.environ.get("NVIDIA_API_KEY") or "").strip() or None
        self.system_prompt = system_prompt
        self.tools = tools
        self._domain = domain

        llm = _build_chat_model(cfg)
        self._agent = create_agent(llm, tools, system_prompt=system_prompt)

    def invoke(
        self,
        question: str,
        chat_history: list | None = None,
        runtime_context: str | None = None,
        allow_context_answer: bool = False,
    ) -> str:
        """Run the agent and return the final answer text. Routes through the
        guarded stream() so tool-use enforcement applies here too."""
        if _MLFLOW_ON:
            import mlflow  # only imported once tracing was explicitly enabled
            with mlflow.start_run(run_name=f"{self._domain}-invoke", nested=True):
                mlflow.set_tags({"domain": self._domain, "question": question[:120]})
                return self._collect_final(
                    question,
                    chat_history,
                    runtime_context,
                    allow_context_answer,
                )
        return self._collect_final(
            question,
            chat_history,
            runtime_context,
            allow_context_answer,
        )

    def _collect_final(
        self,
        question: str,
        chat_history: list | None = None,
        runtime_context: str | None = None,
        allow_context_answer: bool = False,
    ) -> str:
        final = ""
        for ev in self.stream(
            question,
            chat_history,
            runtime_context,
            allow_context_answer,
        ):
            if ev["type"] == "final":
                final = ev["content"]
        return final

    def _drive(self, messages: list, seen_tool_call_ids: set):
        """Stream one agent run. Yields tool_call / tool_result / reasoning events
        live, then one terminal {"type": "_final", "content": ...}."""
        last_ai_content = ""
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
        yield {"type": "_final", "content": last_ai_content}

    def stream(
        self,
        question: str,
        chat_history: list | None = None,
        runtime_context: str | None = None,
        allow_context_answer: bool = False,
    ):
        """
        Stream structured events as the agent works (for Streamlit st.status).
        Yields dicts: reasoning | tool_call | tool_result | final.

        For domains in _ENFORCE_TOOLUSE_DOMAINS, a technical answer that skipped
        its tool triggers ONE strict retry; if that still skips the tool, the
        (untrusted) answer is suppressed in favour of a safe notice.
        """
        # Stateless UI-guide assistants answer each question independently; the
        # stateful engineering assistants keep only the last few turns (long chats
        # otherwise grow the prompt and slow every turn).
        if _is_stateless(self._domain):
            chat_history = None
        else:
            chat_history = _limit_history(chat_history)
        messages = []
        if runtime_context:
            messages.append(("system", runtime_context))
        if chat_history:
            messages.extend(chat_history)
        messages.append(("human", question))

        seen_tool_call_ids: set[str] = set()
        final_content = ""
        for ev in self._drive(messages, seen_tool_call_ids):
            if ev["type"] == "_final":
                final_content = ev["content"]
            else:
                yield ev

        context_answer_allowed = (
            allow_context_answer
            and bool(runtime_context)
            and _is_context_grounded_question(question)
        )
        if (not seen_tool_call_ids and self._domain in _ENFORCE_TOOLUSE_DOMAINS
                and not context_answer_allowed
                and _requires_tool(question, final_content)):
            retry_messages = messages + [
                ("ai", final_content or "(no answer)"),
                ("human", _TOOLUSE_CORRECTION),
            ]
            final_content = ""
            for ev in self._drive(retry_messages, seen_tool_call_ids):
                if ev["type"] == "_final":
                    final_content = ev["content"]
                else:
                    yield ev
            if not seen_tool_call_ids:        # retry STILL answered with no tool
                yield {"type": "final", "content": _TOOLUSE_SAFE_NOTICE}
                return

        if final_content:
            yield {"type": "final", "content": final_content}


def build_agent(domain: str, api_key: str) -> DomainAgent:
    """Construct an agent for a domain: 'shock_mount', 'tiedown', 'mobility',
    or one of the per-tab UI guides (ui_guide_shock/tiedown/mobility)."""
    if domain not in DOMAINS:
        raise KeyError(f"Unknown domain {domain!r}. Available: {list(DOMAINS)}")
    cfg = DOMAINS[domain]
    return DomainAgent(api_key, cfg["prompt"], cfg["tools"], domain=domain)


class ShockMountAgent(DomainAgent):
    """Back-compat: the original shock-mount agent is now a 'shock_mount' DomainAgent."""
    _TOOLS = _SHOCK_TOOLS

    def __init__(self, api_key: str):
        cfg = DOMAINS["shock_mount"]
        super().__init__(api_key, cfg["prompt"], cfg["tools"], domain="shock_mount")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    llm_cfg = resolve_llm_config()
    api_key = llm_cfg.api_key
    if not api_key:
        raise SystemExit(
            f"ERROR: Set {llm_cfg.api_key_env} in your .env file or environment.")

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
        if len(history) > 2 * _MAX_HISTORY_TURNS:
            history = history[-2 * _MAX_HISTORY_TURNS:]
