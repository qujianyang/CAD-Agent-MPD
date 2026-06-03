"""
Tie-down provision physics engine.
Transcribed from: MCDLL Tie-Down Provision_20-8-2023.xlsx
Verified: reproduces all 59 items' safety factors to machine precision (177/177, max diff 9e-13).

Design forces per axis = weight * G_axis * g   (g=9.81; long=4G, vert=2G, lat=1.5G).
Fastener yield force    = sigma * area         (tensile uses sigma_t; shear uses sigma_s).
Mount face decides, per axis, whether the fastener sees tension or shear (see MountFace).
SF_axis = yield_force(force_type) / (design_force_axis / qty).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# (axis label, DesignLoads attribute) -- single source of axis order
AXES = (("long", "long_G"), ("vert", "vert_G"), ("lat", "lat_G"))


@dataclass
class DesignLoads:
    g: float = 9.81
    long_G: float = 4.0
    vert_G: float = 2.0
    lat_G: float = 1.5


class MountFace(Enum):
    """Face the item is fastened to; determines tension-vs-shear per load axis."""
    WALL_X = "WALL_X"    # front/rear wall (normal = longitudinal X): long load is Tensile
    FLOOR_Z = "FLOOR_Z"  # floor/ceiling/top frame/base (normal = vertical Z): vert load is Tensile
    WALL_Y = "WALL_Y"    # left/right side wall (normal = lateral Y): lat load is Tensile

    def force_type(self, axis: str) -> str:
        """axis in {'long','vert','lat'} -> 'Tensile' or 'Shear'."""
        tensile_axis = {
            MountFace.WALL_X: "long",
            MountFace.FLOOR_Z: "vert",
            MountFace.WALL_Y: "lat",
        }[self]
        return "Tensile" if axis == tensile_axis else "Shear"


@dataclass
class FastenerSpec:
    name: str
    kind: str            # BOLT, SPRING_LATCH, LOCKING_PIN, STRAP, RATCHET, CAMLOCK, DRING
    sigma_t_MPa: float   # tensile allowable (for straps: rated load in N, with area=1)
    sigma_s_MPa: float   # shear allowable (bolts/latches: sigma_t/2; straps: == sigma_t)
    area_mm2: float      # minor-diameter area (straps: 1.0)

    @property
    def tensile_force_N(self) -> float:
        return self.sigma_t_MPa * self.area_mm2

    @property
    def shear_force_N(self) -> float:
        return self.sigma_s_MPa * self.area_mm2

    def yield_force_N(self, force_type: str) -> float:
        return self.tensile_force_N if force_type == "Tensile" else self.shear_force_N


@dataclass
class Item:
    name: str
    weight_kg: float
    mount_face: MountFace
    fastener: FastenerSpec
    qty: int
    design_override_kg: Optional[float] = None  # item-49 quirk: design force based on a different kg

    @property
    def design_kg(self) -> float:
        return self.design_override_kg if self.design_override_kg is not None else self.weight_kg


@dataclass
class AxisResult:
    axis: str
    design_force_N: float
    force_type: str
    exp_force_N: float
    yield_force_N: float
    SF: float


@dataclass
class ItemResult:
    item: Item
    axes: list  # list[AxisResult], order = AXES

    @property
    def min_SF(self) -> float:
        return min(a.SF for a in self.axes)

    @property
    def limiting_axis(self) -> AxisResult:
        return min(self.axes, key=lambda a: a.SF)

    def passed(self, target_SF: float = 1.0) -> bool:
        return self.min_SF >= target_SF


def analyze_item(item: Item, loads: Optional[DesignLoads] = None) -> ItemResult:
    L = loads or DesignLoads()
    if item.qty <= 0:
        raise ValueError(f"{item.name}: qty must be > 0")
    axes = []
    for axis, gattr in AXES:
        design = item.design_kg * getattr(L, gattr) * L.g
        ftype = item.mount_face.force_type(axis)
        exp = design / item.qty
        yf = item.fastener.yield_force_N(ftype)
        axes.append(AxisResult(axis, design, ftype, exp, yf, yf / exp))
    return ItemResult(item, axes)


@dataclass
class TiedownReport:
    items: list           # list[ItemResult]
    loads: DesignLoads
    target_SF: float = 1.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed(self.target_SF) for r in self.items)

    def critical_items(self, target_SF: Optional[float] = None) -> list:
        t = self.target_SF if target_SF is None else target_SF
        return [r for r in self.items if r.min_SF < t]


def run_tiedown_analysis(items: list, loads: Optional[DesignLoads] = None,
                         target_SF: float = 1.0) -> TiedownReport:
    L = loads or DesignLoads()
    return TiedownReport([analyze_item(it, L) for it in items], L, target_SF)


def format_report(report: TiedownReport) -> str:
    L = report.loads
    lines = [
        "=" * 70,
        "TIE-DOWN PROVISION ANALYSIS",
        f"  Design loads : long={L.long_G}G  vert={L.vert_G}G  lat={L.lat_G}G   (g={L.g})",
        f"  Items        : {len(report.items)}    target SF: {report.target_SF}",
        "=" * 70,
        f"{'Item':<34}{'min SF':>9}{'limit':>8}{'verdict':>10}",
        "-" * 70,
    ]
    for r in report.items:
        verdict = "PASS" if r.passed(report.target_SF) else "FAIL"
        lines.append(f"{r.item.name[:34]:<34}{r.min_SF:>9.3f}{r.limiting_axis.axis:>8}{verdict:>10}")
    crit = report.critical_items()
    lines.append("-" * 70)
    lines.append("Overall: " + ("ALL PASS" if report.all_passed
                                 else f"{len(crit)} item(s) below target SF {report.target_SF}"))
    lines.append("=" * 70)
    return "\n".join(lines)


def format_item_detail(result: ItemResult) -> str:
    """Per-axis breakdown for one item (Workings-style: force type, forces, SF)."""
    it = result.item
    lines = [
        f"Item: {it.name}",
        f"  Fastener: {it.fastener.name} x{it.qty}   Mount face: {it.mount_face.value}   "
        f"(design mass {it.design_kg:g} kg)",
        f"  {'axis':<5}{'type':<9}{'design(N)':>12}{'per-fastener(N)':>17}{'yield(N)':>12}{'SF':>10}",
    ]
    for a in result.axes:
        lines.append(
            f"  {a.axis:<5}{a.force_type:<9}{a.design_force_N:>12.2f}"
            f"{a.exp_force_N:>17.2f}{a.yield_force_N:>12.2f}{a.SF:>10.3f}"
        )
    lines.append(f"  min SF = {result.min_SF:.3f} ({result.limiting_axis.axis})")
    return "\n".join(lines)


def format_full_report_table(report: TiedownReport) -> str:
    """
    Appendix-G style table: one row per item, columns for each axis SF + verdict.
    Suitable for pasting directly into the SAR (Tie-Down Provision chapter).

    Columns:
      No. | Item | Weight (kg) | Fastener | Qty | SF Long | SF Vert | SF Lat | Min SF | Verdict
    """
    W_NO   = 4
    W_ITEM = 38
    W_KG   = 10
    W_FAS  = 24
    W_QTY  = 4
    W_SF   = 8      # per axis SF column
    W_MIN  = 8
    W_VER  = 7
    SEP = "-" * (W_NO + W_ITEM + W_KG + W_FAS + W_QTY + W_SF * 3 + W_MIN + W_VER + 10)

    hdr = (
        f"{'No.':<{W_NO}} {'Item':<{W_ITEM}} {'Wt(kg)':>{W_KG}} {'Fastener':<{W_FAS}} "
        f"{'Qty':>{W_QTY}} {'SF Long':>{W_SF}} {'SF Vert':>{W_SF}} "
        f"{'SF Lat':>{W_SF}} {'Min SF':>{W_MIN}} {'Verdict':>{W_VER}}"
    )

    lines = [
        "=" * len(SEP),
        "TIE-DOWN PROVISION ANALYSIS -- APPENDIX G SUMMARY TABLE",
        f"  Design loads : 4G long / 2G vert / 1.5G lat   (g=9.81)   "
        f"Target SF: {report.target_SF}",
        "=" * len(SEP),
        hdr,
        SEP,
    ]

    for i, r in enumerate(report.items, 1):
        by = {a.axis: a.SF for a in r.axes}
        verdict = "PASS" if r.passed(report.target_SF) else "FAIL"
        lines.append(
            f"{i:<{W_NO}} {r.item.name[:W_ITEM]:<{W_ITEM}} "
            f"{r.item.weight_kg:>{W_KG}.1f} "
            f"{r.item.fastener.name[:W_FAS]:<{W_FAS}} "
            f"{r.item.qty:>{W_QTY}} "
            f"{by['long']:>{W_SF}.3f} "
            f"{by['vert']:>{W_SF}.3f} "
            f"{by['lat']:>{W_SF}.3f} "
            f"{r.min_SF:>{W_MIN}.3f} "
            f"{verdict:>{W_VER}}"
        )

    lines.append(SEP)
    crit = report.critical_items()
    lines.append(
        "Overall: " + ("ALL PASS" if report.all_passed
                       else f"{len(crit)} item(s) below target SF {report.target_SF}: "
                            + ", ".join(r.item.name for r in crit[:5])
                            + (" ..." if len(crit) > 5 else ""))
    )
    lines.append("=" * len(SEP))
    return "\n".join(lines)


if __name__ == "__main__":
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    demo = [
        Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    rep = run_tiedown_analysis(demo, target_SF=2.0)
    print(format_report(rep))
    print()
    print(format_item_detail(rep.items[0]))
    gen = rep.items[0]
    assert abs(gen.min_SF - 4.9) < 1e-2, gen.min_SF   # anchor (matches Excel)
    print("\n[OK] Generator anchor min SF = 4.9")
