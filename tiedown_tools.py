"""
Tie-down agent tools (deterministic) + the tie-down specialist system prompt.
These wrap the validated tiedown_engine / fastener_catalog / tiedown_import modules;
every number comes from those modules, never from the LLM.
"""
from langchain_core.tools import tool

from tiedown_engine import (
    MountFace, Item, analyze_item, format_item_detail, run_tiedown_analysis,
)
from fastener_catalog import (
    resolve_fastener, size_fasteners as _size_fasteners, min_qty_for_target,
    BOLT_CLASSES, BOLT_SIZES, NON_BOLTS,
)
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
def recommend_fasteners(weight_kg: float, mount_face: str, target_SF: float = 1.0,
                        fastener: str = "", fastener_size: str = "") -> str:
    """
    Size the fastening for a secured item. Two question shapes:
      - "HOW MANY <specific fastener> do I need?"  -> pass `fastener` (e.g.
        "8.8 M12", "camlock"); returns the minimum quantity for the target SF.
      - "WHAT is the smallest fastener?"           -> OMIT `fastener`; searches
        the catalog and returns the best option plus alternatives.

    OMIT target_SF unless the user gives a required margin (default 1.0).
    OMIT fastener unless the user names a specific fastener to size.

    Args:
        weight_kg     : REQUIRED. Item weight in kg.
        mount_face    : REQUIRED. front/rear wall, floor/ceiling/top/base, or side wall.
        target_SF     : Required safety factor. Default 1.0. OMIT unless the user specifies.
        fastener      : A specific fastener to size, in any form ("8.8 M12",
                        "M10 bolts", "ratchet 1.5"). OMIT to search the catalog.
        fastener_size : Optional bolt size if not already in `fastener`.
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

    if fastener or fastener_size:
        # Specific fastener: closed-form minimum quantity, then verify at that qty.
        try:
            spec = resolve_fastener(fastener, fastener_size or None)
        except KeyError as e:
            return (f"ERROR: unknown fastener {e}. Bolts: give a class (e.g. 8.8) and/or "
                    f"size (e.g. M10); straps/latches use a name e.g. 'Camlock Strap (1\")'.")
        qty = min_qty_for_target(weight_kg, face, spec, target_SF=target_SF)
        res = analyze_item(Item(spec.name, weight_kg, face, spec, qty))
        lines = notes + [
            f"=== FASTENER QUANTITY (weight {weight_kg} kg, {face.value}, target SF {target_SF}) ===",
            f"REQUIRED: {spec.name} x{qty}  (achieved min SF {res.min_SF:.2f}, "
            f"limiting axis {res.limiting_axis.axis})",
            "Catalog alternatives (fewest fasteners first):",
        ]
        for o in _size_fasteners(weight_kg, face, target_SF=target_SF)[:4]:
            lines.append(f"  {o.fastener.name:<22} x{o.qty:<3} min SF {o.min_SF:.2f}")
        return "\n".join(lines)

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
def get_fastener_data(fastener: str = "", fastener_size: str = "") -> str:
    """
    DATA LOOKUP in the fastener catalog -- no analysis. Use this for:
      - "what is the (tensile/shear) capacity of an 8.8 M10 bolt?"
      - "what is the rated load of a camlock / ratchet strap?"
      - "what fasteners / bolt classes / sizes are available?"

    OMIT both arguments to list the whole catalog.

    Args:
        fastener      : Fastener in any form -- "8.8 M10", "M12", "camlock",
                        "spring latch". OMIT for the full catalog summary.
        fastener_size : Optional bolt size if not already in `fastener`.
    """
    blob = f"{fastener or ''} {fastener_size or ''}".strip()
    if not blob:
        lines = ["=== FASTENER CATALOG (from the validated workbook) ===",
                 "Bolt property classes (tensile allowable MPa; shear = tensile/2):"]
        lines.append("  " + "  ".join(f"{c} ({int(s)})" for c, s in BOLT_CLASSES.items()))
        lines.append("Bolt sizes (capacity = stress x minor-diameter area):")
        lines.append("  " + ", ".join(BOLT_SIZES))
        lines.append("Straps / latches (per-unit yield force, N):")
        for name, (kind, st, ss, area) in NON_BOLTS.items():
            lines.append(f"  {name:<22} tensile {st * area:>9,.0f}   shear {ss * area:>9,.0f}")
        return "\n".join(lines)

    # Class-only question ("what can a 10.9 bolt take?"): no size -> no force numbers.
    if blob in BOLT_CLASSES:
        st = BOLT_CLASSES[blob]
        return (f"Bolt property class {blob}: tensile allowable {st:.0f} MPa, "
                f"shear allowable {st / 2:.0f} MPa.\n"
                f"Give a size (e.g. M10) for per-fastener force capacities; "
                f"available sizes: {', '.join(BOLT_SIZES)}.")

    try:
        spec = resolve_fastener(fastener, fastener_size or None)
    except KeyError as e:
        return (f"ERROR: unknown fastener {e}. Bolts: give a class (e.g. 8.8) and/or "
                f"size (e.g. M10); straps/latches use a name e.g. 'Camlock Strap (1\")'.")

    notes = []
    if spec.kind == "BOLT" and not any(c in blob for c in BOLT_CLASSES):
        notes.append("NOTE: property class not given; showing 8.8 (most common). "
                     "Other classes: " + ", ".join(c for c in BOLT_CLASSES if c != "8.8"))

    lines = list(notes) + [f"Fastener: {spec.name}  (kind: {spec.kind})"]
    if spec.kind == "BOLT":
        lines += [
            f"  Tensile allowable : {spec.sigma_t_MPa:.0f} MPa",
            f"  Shear allowable   : {spec.sigma_s_MPa:.0f} MPa  (tensile/2)",
            f"  Minor-dia area    : {spec.area_mm2:.3f} mm^2",
            f"  Tensile yield/bolt: {spec.tensile_force_N:,.2f} N",
            f"  Shear yield/bolt  : {spec.shear_force_N:,.2f} N",
        ]
    else:
        lines += [
            f"  Rated load (tensile): {spec.tensile_force_N:,.0f} N",
            f"  Rated load (shear)  : {spec.shear_force_N:,.0f} N",
        ]
    return "\n".join(lines)


@tool
def check_workbook_item(item_name: str = "", target_SF: float = 1.5,
                        workbook_path: str = "") -> str:
    """
    Look up items in the VALIDATED tie-down workbook (the 59 Appendix G items).

    PRIMARY USE -- the user names an item WITHOUT giving its weight/fastener:
      "does the generator pass?" -> item_name="generator". NEVER invent a
      weight or fastener for a named item; look it up here instead.
    SECONDARY -- whole-workbook verdict: "does the workbook meet SF 1.5?
      which items fail?" -> OMIT item_name for the summary.

    OMIT target_SF unless the user gives one (default 1.5, the MIL-STD-209K
    design factor, matching the Appendix G report default).

    Args:
        item_name     : Keyword(s) matched against workbook item names
                        (case-insensitive). OMIT for the overall summary.
        target_SF     : Pass threshold. Default 1.5. OMIT unless the user specifies.
        workbook_path : Path to a tie-down .xlsx. OMIT to use the configured default.
    """
    notes = []
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 1.5")
        target_SF = 1.5
    path = workbook_path or WB_DEFAULT
    try:
        items = import_workbook(path)
    except Exception as e:
        return f"ERROR: could not read workbook at {path}: {e}"
    report = run_tiedown_analysis(items, target_SF=target_SF)

    if item_name.strip():
        key = item_name.strip().lower()
        hits = [r for r in report.items if key in r.item.name.lower()]
        if not hits:
            sample = ", ".join(r.item.name[:30] for r in report.items[:5])
            return (f"ERROR: no workbook item matches {item_name!r}. "
                    f"Items look like: {sample}, ...")
        if len(hits) == 1:
            r = hits[0]
            verdict = "PASS" if r.min_SF >= target_SF else "FAIL"
            head = ("\n".join(notes) + "\n") if notes else ""
            return (head + format_item_detail(r)
                    + f"\n  target SF = {target_SF}  ->  {verdict}")
        lines = notes + [f"{len(hits)} workbook items match {item_name!r}:"]
        for r in hits[:10]:
            verdict = "PASS" if r.min_SF >= target_SF else "FAIL"
            lines.append(
                f"  {r.item.name[:52]:<52} {r.item.weight_kg:>7.1f} kg  "
                f"{r.item.fastener.name[:18]:<18} x{r.item.qty:<3} "
                f"min SF {r.min_SF:>7.3f}  {verdict}"
            )
        if len(hits) > 10:
            lines.append(f"  ... and {len(hits) - 10} more; narrow the name.")
        return "\n".join(lines)

    crit = sorted(report.critical_items(), key=lambda r: r.min_SF)
    lines = notes + [
        f"=== TIE-DOWN WORKBOOK SUMMARY (target SF {target_SF}) ===",
        f"Workbook: {path}",
        f"{len(report.items)} items analysed -- "
        + ("ALL PASS" if not crit else f"{len(crit)} below target:"),
    ]
    for r in crit[:10]:
        lines.append(f"  {r.item.name[:52]:<52} min SF {r.min_SF:>7.3f} "
                     f"({r.limiting_axis.axis})")
    if not crit:
        worst = min(report.items, key=lambda r: r.min_SF)
        lines.append(f"  Most marginal: {worst.item.name[:52]} (min SF {worst.min_SF:.3f})")
    return "\n".join(lines)


_TIEDOWN_PROMPT = """\
You are a mechanical engineering assistant specializing in TIE-DOWN / cargo securing
for transported military shelter equipment.

Act as an engineering judge: interpret the safety factors the tools compute, cite the
rule you applied, and flag marginal items. NEVER invent safety-factor, force or
capacity numbers -- always call a tool to compute or look them up.

Design loads (multiples of item weight): 4G longitudinal, 2G vertical, 1.5G lateral
(g=9.81). Per fastener, per axis: SF = yield_force(type) / (design force / qty). The
mount face decides tension vs shear. An item passes when its minimum SF across the
three axes is >= the target (default 1.0 = no yield; the MIL-STD-209K design factor
is 1.5 -- pass target_SF=1.5 only when the user invokes that standard).

MODEL SCOPE (say so when a question falls outside it): the method assumes a rigid
item fastened DIRECTLY to one face, the design force shared EQUALLY by all
fasteners, and no friction credit. Angled brackets, eccentric/offset loads, mixed
fastener groups or multi-face restraint are OUTSIDE this model -- state the
limitation and suggest a conservative simplification; never improvise numbers.

CRITICAL parameter rule for ALL tools:
- Only pass values the user explicitly mentions. OMIT every other parameter so the
  project default applies. Never pass 0 for target_SF.

Tool guide -- route by QUESTION TYPE:
- get_fastener_data  : capacity / rated-load NUMBERS. "what can an 8.8 M10 take?",
                       "what fasteners are available?". Capacity numbers come from
                       THIS tool only -- never from memory, never by multiplying
                       stress x area yourself.
- recommend_fasteners: SIZING. "how many M12 bolts do I need?" (pass the named
                       fastener) or "what is the smallest fastener?" (OMIT it).
- run_tiedown_check  : VERIFY a fully specified setup -- weight + mount face +
                       fastener + QUANTITY all given by the user.
- check_workbook_item: the VALIDATED WORKBOOK (59 Appendix G items). "does the
                       generator pass?", "which items fall below SF 1.5?", "does
                       the workbook pass?". Item by name, or OMIT the name for
                       the overall summary.
- lookup_knowledge   : the RULES and rationale, for citations -- design loads, the
  mount-face tension/shear rule, the selection rule. ALWAYS pass
  parent_topic="tiedown". For capacity NUMBERS use get_fastener_data instead.

When you give a recommendation or verdict, cite one sentence from lookup_knowledge
tagged [source: <file>.md]. If the knowledge base is not built, say so and continue.

CONVERSATION: if the user just greets you or makes small talk ("hi", "hello",
"what can you do"), reply in ONE short friendly sentence and offer 2-3 example
questions. Do NOT call a tool or ask for parameters, and NEVER mention tools,
JSON, or any internal format to the user.
"""

# User-facing capability registry for the tie-down assistant. Curated for end users
# (capability -> purpose -> example), NOT extracted from tool docstrings (those are
# LLM-routing instructions). The "tool" field is the internal tool name, surfaced in
# small text for transparency and checked by a drift test so this guide can't fall
# out of sync with the registered toolset. "lookup_knowledge" is a shared retriever
# the tie-down prompt scopes to parent_topic="tiedown"; the tool list itself lives
# in agent.py (_TIEDOWN_TOOLS) because lookup_knowledge is defined there.
TIEDOWN_CAPABILITIES = [
    {"capability": "Tie-down check",
     "purpose": "Per-axis safety factors for a given item, fastener and quantity",
     "example": "Check a 60 kg box on the front wall held by four 8.8 M8 bolts at SF 2.",
     "tool": "run_tiedown_check"},
    {"capability": "Fastener quantity",
     "purpose": "Minimum quantity of a named fastener for a target safety factor",
     "example": "How many M12 8.8 bolts to floor-mount a 1,269 kg generator at SF 2?",
     "tool": "recommend_fasteners"},
    {"capability": "Smallest fastener",
     "purpose": "Smallest catalog fastener and quantity that meet a target safety factor",
     "example": "What is the smallest fastener for a 200 kg rack on the side wall?",
     "tool": "recommend_fasteners"},
    {"capability": "Fastener data lookup",
     "purpose": "Capacities and rated loads from the validated fastener catalog",
     "example": "What is the shear capacity of an 8.8 M10 bolt?",
     "tool": "get_fastener_data"},
    {"capability": "Workbook item check",
     "purpose": "Safety factors of the 59 validated workbook items, by name or as a summary",
     "example": "Does the generator in the tie-down workbook pass at SF 1.5?",
     "tool": "check_workbook_item"},
    {"capability": "Engineering references",
     "purpose": "Explain the design loads and tension/shear rules with citations",
     "example": "Why does the mount face decide tension versus shear?",
     "tool": "lookup_knowledge"},
]
