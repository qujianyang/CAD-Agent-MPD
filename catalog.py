"""
CB1400 Wire Rope Isolator catalog + automated part selection.
Catalog data: datasheet 137R-103480 REV:5 (1/2" Wire Rope, CB1400 Series).

Selection logic:
  - GT must be below GT_limit for ALL directions (compression + shear)
  - Dynamic deflection must be below isolator's max travel for ALL directions
  - Among all valid candidates, prefer the SOFTEST (lowest K) that still passes.
    Softer = lower transmitted G = better isolation.
"""
import math
from dataclasses import dataclass, field
from typing import Optional

from physics_engine import (
    IsolatorSpec, ShockEnv, DirectionResult, PhysicsReport,
    _calc_direction, _loads_per_isolator, run_analysis, format_report,
)

_LB_IN_TO_N_M = 175.1268   # 1 lb/in = 175.1268 N/m
_IN_TO_MM     = 25.4        # 1 inch  = 25.4 mm


# ---------------------------------------------------------------------------
# Catalog data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogEntry:
    part_no: str
    H_in: float             # Nominal height [in]
    W_in: float             # Nominal width [in]
    k_comp_lbin: float      # Shock Average K — Compression [lb/in]
    k_shear_lbin: float     # Shock Average K — Shear/Roll [lb/in]
    d_max_comp_in: float    # Max Rated Dynamic Travel — Compression [in]
    d_max_shear_in: float   # Max Rated Dynamic Travel — Shear/Roll [in]

    # ---- unit-converted properties ----
    @property
    def k_comp_Nm(self)      -> float: return self.k_comp_lbin  * _LB_IN_TO_N_M
    @property
    def k_shear_Nm(self)     -> float: return self.k_shear_lbin * _LB_IN_TO_N_M
    @property
    def d_max_comp_mm(self)  -> float: return self.d_max_comp_in  * _IN_TO_MM
    @property
    def d_max_shear_mm(self) -> float: return self.d_max_shear_in * _IN_TO_MM

    def to_isolator_spec(self) -> IsolatorSpec:
        return IsolatorSpec(
            name=self.part_no,
            k_comp_Nm=self.k_comp_Nm,
            k_shear_Nm=self.k_shear_Nm,
            d_max_comp_mm=self.d_max_comp_mm,
            d_max_shear_mm=self.d_max_shear_mm,
        )


# All 10 variants — data read from 137R-103480 REV:5
CB1400_CATALOG: list[CatalogEntry] = [
    #                          part_no        H      W     Kcomp  Kshear  dComp  dShear
    CatalogEntry("CB1400-10", 3.00, 3.31,  3515,  1801,  1.10,  1.10),
    CatalogEntry("CB1400-12", 3.00, 3.63,  3145,  1531,  1.20,  1.20),
    CatalogEntry("CB1400-15", 3.25, 4.00,  2650,  1080,  1.40,  1.60),
    CatalogEntry("CB1400-17", 3.50, 4.13,  2090,   865,  1.60,  1.80),
    CatalogEntry("CB1400-20", 3.75, 4.75,  1365,   740,  2.00,  2.00),
    CatalogEntry("CB1400-25", 4.00, 5.00,  1135,   580,  2.20,  2.20),
    CatalogEntry("CB1400-30", 4.25, 5.25,   905,   420,  2.40,  2.40),
    CatalogEntry("CB1400-40", 4.90, 5.65,   665,   320,  2.80,  2.80),
    CatalogEntry("CB1400-50", 5.40, 6.13,   500,   260,  3.20,  3.20),
    CatalogEntry("CB1400-60", 6.10, 7.10,   265,   145,  4.00,  3.60),
]


# ---------------------------------------------------------------------------
# Selection result
# ---------------------------------------------------------------------------

@dataclass
class CatalogCandidate:
    entry: CatalogEntry
    comp_vertical:   DirectionResult   # Compression, Z (bottom mounts)
    comp_horizontal: DirectionResult   # Compression, Y (wall mounts)
    shear_horizontal: DirectionResult  # Shear/Roll, X & Z

    @property
    def valid(self) -> bool:
        return (self.comp_vertical.passed and
                self.comp_horizontal.passed and
                self.shear_horizontal.passed)

    @property
    def worst_GT_ratio(self) -> float:
        """Max GT/limit across all directions. < 1.0 = pass. Closer to 0 = more margin."""
        return max(d.GT_G / d.GT_limit for d in self._dirs)

    @property
    def worst_delta_ratio(self) -> float:
        return max(d.delta_mm / d.delta_limit_mm for d in self._dirs)

    @property
    def limiting_direction(self) -> DirectionResult:
        return max(self._dirs, key=lambda d: d.GT_G / d.GT_limit)

    @property
    def _dirs(self):
        return [self.comp_vertical, self.comp_horizontal, self.shear_horizontal]


# ---------------------------------------------------------------------------
# Core selection
# ---------------------------------------------------------------------------

def select_isolator(
    m_comp_vertical_kg: float,
    m_horizontal_kg: float,
    env: ShockEnv,
    g: float = 9.81,
) -> list[CatalogCandidate]:
    """
    Evaluate every CB1400 catalog entry against the load and shock environment.

    Returns all candidates sorted: valid first, then by ascending K_comp (softest first).
    The first entry in the returned list is the RECOMMENDED part.

    Why softest first?
      Lower K → lower fn → lower GT (less shock transmitted).
      We want the best isolation that still keeps dD within the isolator's travel limit.
    """
    candidates = []
    for entry in CB1400_CATALOG:
        spec = entry.to_isolator_spec()
        comp_v  = _calc_direction("Compression - Z (vertical)",   spec.k_comp_Nm,  m_comp_vertical_kg, spec.d_max_comp_mm,  env, g)
        comp_h  = _calc_direction("Compression - Y (lateral)",    spec.k_comp_Nm,  m_horizontal_kg,    spec.d_max_comp_mm,  env, g)
        shear_h = _calc_direction("Shear/Roll   - X & Z",         spec.k_shear_Nm, m_horizontal_kg,    spec.d_max_shear_mm, env, g)
        candidates.append(CatalogCandidate(entry, comp_v, comp_h, shear_h))

    # Sort: valid PASS entries first, then within each group sort by softest (lowest K)
    candidates.sort(key=lambda c: (not c.valid, c.entry.k_comp_lbin))
    return candidates


def select_and_analyze(
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    cad_props: Optional[dict] = None,
    shock_env: Optional[ShockEnv] = None,
    g: float = 9.81,
) -> tuple[PhysicsReport, list[CatalogCandidate]]:
    """
    Full pipeline:
      1. Compute load per isolator from mass + mount count
      2. Scan catalog → find valid candidates
      3. Run PhysicsReport with the recommended (softest valid) part
      4. Return both for downstream use (LLM context, UI display)
    """
    env   = shock_env or ShockEnv()
    loads = _loads_per_isolator(mass_kg, n_bottom, n_wall)

    candidates = select_isolator(
        loads["m_comp_vertical_kg"],
        loads["m_horizontal_kg"],
        env, g=g,
    )

    best = next((c for c in candidates if c.valid), None)
    selected_spec = best.entry.to_isolator_spec() if best else None

    report = run_analysis(
        mass_kg, n_bottom, n_wall,
        cad_props=cad_props,
        shock_env=env,
        isolator=selected_spec,
        g=g,
    )
    return report, candidates


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_selection_table(candidates: list[CatalogCandidate]) -> str:
    """
    ASCII table: all catalog entries with computed GT, dD, and PASS/FAIL.
    Shows the engineer every option at a glance.
    """
    header = (
        f"{'Part':<14} {'Kcomp':>8} {'Kshear':>8} | "
        f"{'Vt-Z GT':>8} {'Vt-Z dD':>8} | "
        f"{'La-Y GT':>8} | "
        f"{'Sr GT':>8} {'Sr dD':>8} | "
        f"{'STATUS':>6}"
    )
    sep = "-" * len(header)
    lines = [
        "=" * len(header),
        "CB1400 SERIES — SELECTION MATRIX (Shock Average K, Saw-Tooth 20G / 11ms)",
        f"{'':14} {'lb/in':>8} {'lb/in':>8} | "
        f"{'[G]':>8} {'[mm]':>8} | "
        f"{'[G]':>8} | "
        f"{'[G]':>8} {'[mm]':>8} | "
        f"{'':>6}",
        header,
        sep,
    ]
    for c in candidates:
        cv, ch, sh = c.comp_vertical, c.comp_horizontal, c.shear_horizontal
        status = "PASS" if c.valid else "FAIL"
        lines.append(
            f"{c.entry.part_no:<14} "
            f"{c.entry.k_comp_lbin:>8.0f} "
            f"{c.entry.k_shear_lbin:>8.0f} | "
            f"{cv.GT_G:>8.3f} "
            f"{cv.delta_mm:>8.1f} | "
            f"{ch.GT_G:>8.3f} | "
            f"{sh.GT_G:>8.3f} "
            f"{sh.delta_mm:>8.1f} | "
            f"{status:>6}"
        )
    lines.append("=" * len(header))

    valid_list = [c for c in candidates if c.valid]
    if valid_list:
        rec = valid_list[0]
        lines.append(
            f"\nRECOMMENDED: {rec.entry.part_no}  "
            f"(H={rec.entry.H_in}\" x W={rec.entry.W_in}\" | "
            f"worst GT ratio: {rec.worst_GT_ratio:.2%} of limit)"
        )
        lines.append(_math_proof(rec))
    else:
        lines.append("\nNO VALID PART FOUND. Options: increase n_mounts OR relax GT_limit OR change shock profile.")

    return "\n".join(lines)


def _math_proof(c: CatalogCandidate) -> str:
    """
    Step-by-step proof block for the recommended part — satisfies Feature 4
    (transparent engineering validation: shows formulas + values + limits).
    """
    e = c.entry
    lines = [
        f"\nMATHEMATICAL PROOF — {e.part_no}",
        f"  K_comp  = {e.k_comp_lbin} lb/in  ->  {e.k_comp_Nm:,.0f} N/m",
        f"  K_shear = {e.k_shear_lbin} lb/in  ->  {e.k_shear_Nm:,.0f} N/m",
        f"  dMax_comp  = {e.d_max_comp_in} in  ->  {e.d_max_comp_mm:.2f} mm",
        f"  dMax_shear = {e.d_max_shear_in} in  ->  {e.d_max_shear_mm:.2f} mm",
    ]
    for d in c._dirs:
        ok = "PASS" if d.passed else "FAIL"
        lines += [
            f"\n  [{ok}] {d.label}",
            f"    m   = {d.m_kg:.2f} kg  (mass per isolator)",
            f"    V   = 0.5 x g x Ao x to          = {d.V_ms:.4f} m/s",
            f"    fn  = (1/2pi) x sqrt(K/m)         = {d.fn_Hz:.4f} Hz",
            f"    GT  = (2pi x fn x V) / g          = {d.GT_G:.4f} G    limit={d.GT_limit} G  -> {'OK' if d.GT_ok else 'FAIL'}",
            f"    dD  = V / (2pi x fn)              = {d.delta_mm:.4f} mm  limit={d.delta_limit_mm:.2f} mm -> {'OK' if d.delta_ok else 'FAIL'}",
        ]
    return "\n".join(lines)


def selection_context_for_llm(candidates: list[CatalogCandidate]) -> str:
    """
    Compact summary injected into LLM system prompt so the AI explains
    the recommendation rather than inventing its own numbers.
    """
    valid = [c for c in candidates if c.valid]
    fail  = [c for c in candidates if not c.valid]
    rec   = valid[0] if valid else None

    parts = []
    parts.append("=== CATALOG SELECTION RESULTS ===")
    if rec:
        d = rec.limiting_direction
        parts.append(
            f"RECOMMENDED PART: {rec.entry.part_no}\n"
            f"  K_comp = {rec.entry.k_comp_lbin} lb/in | K_shear = {rec.entry.k_shear_lbin} lb/in\n"
            f"  Limiting direction: {d.label}\n"
            f"    fn={d.fn_Hz:.2f} Hz | GT={d.GT_G:.2f} G (limit {d.GT_limit} G) | "
            f"dD={d.delta_mm:.1f} mm (limit {d.delta_limit_mm:.1f} mm)"
        )
        parts.append(f"  Also valid (softer alternatives): " +
                     ", ".join(c.entry.part_no for c in valid[1:]) if len(valid) > 1 else "  No softer alternative passes.")
    else:
        parts.append("NO VALID PART FOUND in CB1400 catalog for this load/shock combination.")
    parts.append(f"Parts that FAIL: " + ", ".join(c.entry.part_no for c in fail))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    env = ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0)
    report, candidates = select_and_analyze(
        mass_kg=850.0, n_bottom=6, n_wall=4, shock_env=env
    )
    print(format_selection_table(candidates))
    print()
    print(format_report(report))
