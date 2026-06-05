"""
Tie-down agent tools (deterministic) + the tie-down specialist system prompt.
These wrap the validated tiedown_engine / fastener_catalog / tiedown_import modules;
every number comes from those modules, never from the LLM.
"""
from langchain_core.tools import tool

from tiedown_engine import MountFace, Item, analyze_item, run_tiedown_analysis, format_item_detail
from fastener_catalog import make_fastener, resolve_fastener, size_fasteners as _size_fasteners
from tiedown_import import import_workbook, WB_DEFAULT

_FACE_ALIASES = {
    "wall_x": MountFace.WALL_X, "x": MountFace.WALL_X, "front": MountFace.WALL_X,
    "front wall": MountFace.WALL_X, "rear": MountFace.WALL_X, "rear wall": MountFace.WALL_X,
    "floor_z": MountFace.FLOOR_Z, "z": MountFace.FLOOR_Z, "floor": MountFace.FLOOR_Z,
    "ceiling": MountFace.FLOOR_Z, "top": MountFace.FLOOR_Z, "base": MountFace.FLOOR_Z,
    "wall_y": MountFace.WALL_Y, "y": MountFace.WALL_Y, "side": MountFace.WALL_Y,
    "side wall": MountFace.WALL_Y, "left": MountFace.WALL_Y, "right": MountFace.WALL_Y,
}


def _parse_face(s: str):
    return _FACE_ALIASES.get((s or "").strip().lower())


_FACE_HELP = ("mount_face must be one of: front/rear wall (WALL_X), "
              "floor/ceiling/top/base (FLOOR_Z), or left/right side wall (WALL_Y).")


@tool
def run_tiedown_check(weight_kg: float, mount_face: str, fastener: str,
                      qty: int, fastener_size: str = "", target_SF: float = 1.0) -> str:
    """
    Check whether a secured item's fasteners survive the transport design loads
    (4G longitudinal, 2G vertical, 1.5G lateral). Returns per-axis safety factors
    (tension vs shear set by the mount face) and a PASS/FAIL verdict.

    OMIT target_SF unless the user gives a required margin (default 1.0 = no yield).

    Args:
        weight_kg     : REQUIRED. Item weight in kg.
        mount_face    : REQUIRED. front/rear wall, floor/ceiling/top/base, or side wall.
        fastener      : REQUIRED. For a bolt give the grade and/or size in any
                        form -- "8.8", "M10", "8.8 M10", even "M10 bolts" (grade
                        defaults to 8.8 if unspecified). For a strap/latch give a
                        name/keyword: "camlock", "ratchet", "spring latch".
        qty           : REQUIRED. Number of fasteners installed.
        fastener_size : Optional bolt size ("M6".."M12"). May be left empty if the
                        size is already in `fastener`.
        target_SF     : Pass threshold. Default 1.0. OMIT unless the user specifies.
    """
    notes = []
    face = _parse_face(mount_face)
    if face is None:
        return f"ERROR: unknown mount_face {mount_face!r}. {_FACE_HELP}"
    if weight_kg <= 0:
        return "ERROR: weight_kg must be positive."
    if qty <= 0:
        return "ERROR: qty must be a positive integer."
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 1.0")
        target_SF = 1.0
    try:
        spec = resolve_fastener(fastener, fastener_size or None)
    except KeyError as e:
        return (f"ERROR: unknown fastener {e}. Bolts: give a class (e.g. 8.8) and/or "
                f"size (e.g. M10); straps/latches use a name e.g. 'Camlock Strap (1\")'.")
    res = analyze_item(Item(spec.name, weight_kg, face, spec, int(qty)))
    verdict = "PASS" if res.min_SF >= target_SF else "FAIL"
    head = ("\n".join(notes) + "\n") if notes else ""
    return head + format_item_detail(res) + f"\n  target SF = {target_SF}  ->  {verdict}"


@tool
def recommend_fasteners(weight_kg: float, mount_face: str, target_SF: float = 1.0) -> str:
    """
    Recommend the smallest fastener + quantity that achieves the target safety factor
    for a secured item (the tie-down analog of choosing the softest valid isolator).
    Returns the best option plus alternatives.

    OMIT target_SF unless the user gives a required margin (default 1.0).

    Args:
        weight_kg  : REQUIRED. Item weight in kg.
        mount_face : REQUIRED. front/rear wall, floor/ceiling/top/base, or side wall.
        target_SF  : Required safety factor. Default 1.0. OMIT unless the user specifies.
    """
    notes = []
    face = _parse_face(mount_face)
    if face is None:
        return f"ERROR: unknown mount_face {mount_face!r}. {_FACE_HELP}"
    if weight_kg <= 0:
        return "ERROR: weight_kg must be positive."
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 1.0")
        target_SF = 1.0
    opts = _size_fasteners(weight_kg, face, target_SF=target_SF)
    best = opts[0]
    lines = notes + [
        f"=== FASTENER SIZING (weight {weight_kg} kg, {face.value}, target SF {target_SF}) ===",
        f"RECOMMENDED: {best.fastener.name} x{best.qty}  (achieved min SF {best.min_SF:.2f})",
        "Alternatives (fewest fasteners first):",
    ]
    for o in opts[1:5]:
        lines.append(f"  {o.fastener.name:<22} x{o.qty:<3} min SF {o.min_SF:.2f}")
    return "\n".join(lines)


@tool
def flag_critical_items(target_SF: float = 2.0, workbook_path: str = "") -> str:
    """
    Import the tie-down provision workbook and list the items whose minimum safety
    factor falls below a target margin (the marginal / at-risk items).

    OMIT both parameters to use the defaults (target_SF=2.0, the configured workbook).

    Args:
        target_SF     : Margin to flag against. Default 2.0. OMIT unless the user specifies.
        workbook_path : Path to a tie-down .xlsx. OMIT to use the configured default.
    """
    notes = []
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 2.0")
        target_SF = 2.0
    path = workbook_path or WB_DEFAULT
    try:
        items = import_workbook(path)
    except Exception as e:
        return f"ERROR: could not read workbook at {path}: {e}"
    report = run_tiedown_analysis(items, target_SF=target_SF)
    crit = sorted(report.critical_items(), key=lambda r: r.min_SF)
    lines = notes + [
        f"=== CRITICAL ITEMS (min SF < {target_SF}) ===",
        f"Workbook: {path}",
        f"{len(crit)} of {len(items)} items below target:",
    ]
    for r in crit:
        lines.append(f"  {r.item.name[:40]:<40} min SF {r.min_SF:>7.3f} ({r.limiting_axis.axis})")
    if not crit:
        lines.append("  (none -- all items meet the target)")
    return "\n".join(lines)


_TIEDOWN_PROMPT = """\
You are a mechanical engineering assistant specializing in TIE-DOWN / cargo securing
for transported military shelter equipment.

Act as an engineering judge: interpret the safety factors the tools compute, cite the
rule you applied, and flag marginal items. NEVER invent safety-factor or force numbers
-- always call a tool to compute them.

Design loads (multiples of item weight): 4G longitudinal, 2G vertical, 1.5G lateral
(g=9.81). Per fastener, per axis: SF = yield_force(type) / (design force / qty). The
mount face decides tension vs shear. An item passes when its minimum SF across the
three axes is >= the target (default 1.0).

CRITICAL parameter rule for ALL tools:
- Only pass values the user explicitly mentions. OMIT every other parameter so the
  project default applies. Never pass 0 for target_SF.

Tool guide:
- run_tiedown_check  : verify a specific item + fastener + quantity.
- recommend_fasteners: size the smallest fastener + quantity for a target SF.
- flag_critical_items: list items below a margin (default SF 2.0) from the workbook.
- lookup_knowledge   : ALWAYS pass parent_topic="tiedown". Use it to cite the design
  loads, the mount-face tension/shear rule, fastener capacities, or the selection rule.

When you give a recommendation or verdict, cite one sentence from lookup_knowledge
tagged [source: <file>.md]. If the knowledge base is not built, say so and continue.

CONVERSATION: if the user just greets you or makes small talk ("hi", "hello",
"what can you do"), reply in ONE short friendly sentence and offer 2-3 example
questions. Do NOT call a tool or ask for parameters, and NEVER mention tools,
JSON, or any internal format to the user.
"""
