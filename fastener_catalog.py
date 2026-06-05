"""
Fastener catalog for tie-down sizing.
Transcribed verbatim from the 'Fastener Data' sheet of
MCDLL Tie-Down Provision_20-8-2023.xlsx.

Bolts: sigma_s = sigma_t / 2.  Straps/ratchets: sigma_s = sigma_t, area = 1
(the value is a rated load in N).  Spring latch / locking pin: real area, sigma_s = sigma_t/2.
"""
import math
import re
from dataclasses import dataclass
from typing import Optional

from tiedown_engine import DesignLoads, MountFace, FastenerSpec, Item, AXES, analyze_item

# Property class -> tensile allowable stress (MPa); shear taken as half.
BOLT_CLASSES = {
    "A2-70": 450.0, "4.6": 240.0, "4.8": 340.0, "5.8": 420.0,
    "8.8": 640.0, "9.8": 720.0, "10.9": 940.0, "12.9": 1100.0,
}

# Bolt size -> minor-diameter area (mm^2). Full precision from the sheet.
BOLT_SIZES = {
    "M1.6": 1.0762, "M2": 1.789, "M2.5": 2.9801, "M3": 4.4734, "M3.5": 5.9997,
    "M4": 7.7496, "M5": 12.683, "M6": 17.894, "M8": 32.841, "M10": 52.292,
    "M12": 76.247, "M14": 104.71, "M16": 144.12, "M20": 225.19, "M22": 281.53,
    "M24": 324.27, "M27": 427.09, "M30": 518.99, "M33": 647.19, "M36": 759.28,
    "1/4-20": 21.711908771848677,
}

# Non-bolt fasteners -> (kind, sigma_t, sigma_s, area).
NON_BOLTS = {
    'Camlock Strap (1")': ("CAMLOCK", 2500.0, 2500.0, 1.0),
    'Camlock Strap (1.5")': ("CAMLOCK", 18000.0, 18000.0, 1.0),
    'Ratchet (1")': ("RATCHET", 5000.0, 5000.0, 1.0),
    'Ratchet (1.5")': ("RATCHET", 30000.0, 30000.0, 1.0),
    "Strap (Net)": ("STRAP", 3500.0, 3500.0, 1.0),
    "DRing": ("DRING", 8896.0, 8896.0, 1.0),
    "Spring Latch": ("SPRING_LATCH", 165.0, 82.5, 113.09733552923255),
    "Locking Pin": ("LOCKING_PIN", 250.0, 125.0, 28.274333882308138),
}


def bolt(class_name: str, size: str) -> FastenerSpec:
    st = BOLT_CLASSES[class_name]
    return FastenerSpec(f"{class_name} {size}", "BOLT", st, st / 2.0, BOLT_SIZES[size])


def non_bolt(name: str) -> FastenerSpec:
    kind, st, ss, area = NON_BOLTS[name]
    return FastenerSpec(name, kind, st, ss, area)


def make_fastener(class_or_name: str, size: Optional[str] = None) -> FastenerSpec:
    if size is not None and size in BOLT_SIZES and class_or_name in BOLT_CLASSES:
        return bolt(class_or_name, size)
    if class_or_name in NON_BOLTS:
        return non_bolt(class_or_name)
    raise KeyError(f"Unknown fastener: class_or_name={class_or_name!r} size={size!r}")


# --- forgiving resolver: tolerate messy LLM/user input ----------------------
_CLASS_RE = re.compile(r"(?<!\d)(\d{1,2}\.\d)(?!\d)")     # 8.8, 10.9, 4.6, 12.9
_SIZE_RE  = re.compile(r"\bM\s?(\d+(?:\.\d+)?)\b", re.I)  # M10, M 10, M2.5

# distinctive keyword -> NON_BOLTS key resolver
_STRAP_KW = [
    ("camlock",      lambda s: 'Camlock Strap (1.5")' if "1.5" in s else 'Camlock Strap (1")'),
    ("ratchet",      lambda s: 'Ratchet (1.5")' if "1.5" in s else 'Ratchet (1")'),
    ("spring latch", lambda s: "Spring Latch"),
    ("locking pin",  lambda s: "Locking Pin"),
    ("d-ring",       lambda s: "DRing"),
    ("dring",        lambda s: "DRing"),
    ("net",          lambda s: "Strap (Net)"),
    ("strap",        lambda s: "Strap (Net)"),     # generic strap fallback
]


def resolve_fastener(fastener: str, size: Optional[str] = None) -> FastenerSpec:
    """
    Tolerant fastener lookup. Accepts messy inputs and extracts the right spec:
      "8.8", "M10"          -> 8.8 M10 bolt
      "M10 8.8" / "8.8 M10" -> 8.8 M10 bolt (order-independent)
      "8x M10 bolts"        -> 8.8 M10 bolt (class defaults to 8.8 if unspecified)
      "camlock 1 inch"      -> Camlock Strap (1")
      "spring latch"        -> Spring Latch
    Raises KeyError only when nothing recognisable is present.
    """
    blob = f"{fastener or ''} {size or ''}".strip()
    low = blob.lower()

    # fast path: already-exact inputs
    if fastener in NON_BOLTS:
        return non_bolt(fastener)
    if fastener in BOLT_CLASSES and size in BOLT_SIZES:
        return bolt(fastener, size)

    # bolt class + size from anywhere in the text
    cls = "A2-70" if ("a2-70" in low or "a2 70" in low) else None
    if cls is None:
        m = _CLASS_RE.search(blob)
        if m and m.group(1) in BOLT_CLASSES:
            cls = m.group(1)
    sz = None
    ms = _SIZE_RE.search(blob)
    if ms:
        cand = "M" + ms.group(1)
        if cand in BOLT_SIZES:
            sz = cand
    if sz and not cls:
        cls = "8.8"            # most common structural grade when unspecified
    if cls and sz:
        return bolt(cls, sz)

    # strap / latch by keyword
    for kw, resolver in _STRAP_KW:
        if kw in low:
            name = resolver(low)
            if name in NON_BOLTS:
                return non_bolt(name)

    raise KeyError(f"could not resolve a fastener from {fastener!r} (size {size!r})")


@dataclass
class SizingOption:
    fastener: FastenerSpec
    qty: int
    min_SF: float


def min_qty_for_target(weight_kg: float, mount_face: MountFace, fastener: FastenerSpec,
                       target_SF: float = 1.0, loads: Optional[DesignLoads] = None) -> int:
    """Closed form: SF_axis = qty * yield(type) / design_axis, so
    min qty = ceil(max over axes of target_SF * design_axis / yield(type))."""
    L = loads or DesignLoads()
    need = 0.0
    for axis, gattr in AXES:
        design = weight_kg * getattr(L, gattr) * L.g
        yf = fastener.yield_force_N(mount_face.force_type(axis))
        need = max(need, target_SF * design / yf)
    return max(1, math.ceil(need))


# Default search pool for the sizing tool: common 8.8 bolts + the rated straps/latch.
DEFAULT_POOL = [
    bolt("8.8", "M6"), bolt("8.8", "M8"), bolt("8.8", "M10"), bolt("8.8", "M12"),
    non_bolt('Camlock Strap (1")'), non_bolt('Camlock Strap (1.5")'),
    non_bolt('Ratchet (1")'), non_bolt("Spring Latch"),
]


def size_fasteners(weight_kg: float, mount_face: MountFace, target_SF: float = 1.0,
                   pool: Optional[list] = None, loads: Optional[DesignLoads] = None) -> list:
    """Return sizing options (smallest valid first): fewest fasteners, then real bolts
    by area (sentinel-area straps/latches lose size ties so they cannot masquerade as 'smallest')."""
    pool = pool if pool is not None else DEFAULT_POOL
    L = loads or DesignLoads()
    opts = []
    for spec in pool:
        q = min_qty_for_target(weight_kg, mount_face, spec, target_SF, L)
        res = analyze_item(Item(spec.name, weight_kg, mount_face, spec, q), L)
        opts.append(SizingOption(spec, q, res.min_SF))
    opts.sort(key=lambda o: (o.qty, 0 if o.fastener.kind == "BOLT" else 1, o.fastener.area_mm2))
    return opts
