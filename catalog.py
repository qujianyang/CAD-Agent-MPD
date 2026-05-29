"""
Wire Rope Isolator catalog + automated part selection.
Covers CB61400 (6-strand 1/2"), CB1400 (1/2"), CB1500 (5/8"), CB1700 (7/8") series.

Data sources (all from Helical / Aeroflex datasheet PDF supplied by supervisor):
  CB61400 — Helical CB6 1400 Series, 1/2" 6-strand wire rope
  CB1400  — Helical CB 1400 Series, 1/2" wire rope (datasheet 137R-103480 REV:5)
  CB1500  — Helical CB 1500 Series, 5/8" wire rope
  CB1700  — Helical CB 1700 Series, 7/8" wire rope
  NOTE: CB1800 removed — not present in the official Helical catalog.
        Supervisor's stated range is C1260 to CB1700.

Selection logic:
  - GT must be below GT_limit for ALL directions (compression + shear)
  - Dynamic deflection must be below isolator's max travel for ALL directions
  - Among all valid candidates, prefer the SOFTEST (lowest K) that still passes.
    Softer = lower transmitted G = better isolation.
  - By default all four series are scanned; pass catalog=CB1400_CATALOG etc. to restrict.
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

# Sentinel "no clearance constraint" — large enough that min(dmax, this) == dmax,
# so leaving clearance blank reproduces the original (travel-limited) behaviour.
_NO_CLEARANCE_MM = 1.0e9

# Valid selection objectives (tiebreak among parts that pass all 4 cases).
SELECT_OBJECTIVES = ("best_isolation", "max_clearance", "balanced")


# ---------------------------------------------------------------------------
# Catalog entry dataclass
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

    @property
    def series(self) -> str:
        """Derive series name from part number, e.g. 'CB1400-15' → 'CB1400'."""
        return self.part_no.rsplit("-", 1)[0]

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


# ---------------------------------------------------------------------------
# CB61400 — 6-strand helical, 1/2" wire rope  (7 variants, Helical datasheet)
# Same physical size as CB1400 but ~25% softer due to 6-strand construction.
# Supervisor explicitly provided this series for inclusion.
# ---------------------------------------------------------------------------
CB61400_CATALOG: list[CatalogEntry] = [
    #                            part_no          H      W    Kcomp  Kshear  dComp  dShear
    CatalogEntry("CB61400-15", 3.25, 4.00,  1990,   810,  1.40,  1.60),
    CatalogEntry("CB61400-17", 3.50, 4.13,  1570,   650,  1.60,  1.80),
    CatalogEntry("CB61400-20", 3.75, 4.75,  1025,   555,  2.00,  2.00),
    CatalogEntry("CB61400-30", 4.25, 5.25,   680,   315,  2.40,  2.40),
    CatalogEntry("CB61400-40", 4.90, 5.65,   500,   240,  2.80,  2.80),
    CatalogEntry("CB61400-50", 5.40, 6.13,   375,   195,  3.20,  3.20),
    CatalogEntry("CB61400-60", 6.10, 7.10,   200,   110,  4.00,  3.60),
]

# ---------------------------------------------------------------------------
# CB1400 — 1/2" wire rope  (10 variants, datasheet REV:5)
# Note: -10, -12, -25 variants are from REV:5 datasheet; the Helical PDF
# supplied by supervisor only lists -15 through -60. Kept for completeness.
# ---------------------------------------------------------------------------
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
# CB1500 — 5/8" wire rope  (6 variants, datasheet REV:6 / VMC catalog 706-C)
# ---------------------------------------------------------------------------
CB1500_CATALOG: list[CatalogEntry] = [
    #                          part_no        H      W     Kcomp  Kshear  dComp  dShear
    CatalogEntry("CB1500-12", 3.50, 4.00,  5375,  2735,  1.20,  1.20),
    CatalogEntry("CB1500-15", 3.90, 4.40,  3655,  1870,  1.40,  1.40),
    CatalogEntry("CB1500-20", 4.30, 5.30,  2585,  1250,  1.80,  1.80),
    CatalogEntry("CB1500-30", 4.70, 6.00,  1610,   800,  2.20,  2.20),
    CatalogEntry("CB1500-40", 5.00, 6.50,  1155,   560,  2.40,  2.40),
    CatalogEntry("CB1500-50", 5.30, 7.00,   795,   410,  3.20,  3.20),
]

# ---------------------------------------------------------------------------
# CB1700 — 7/8" wire rope  (5 variants, Helical datasheet p.16)
# Replaces CB1800 which does not appear in the official Helical catalog.
# Supervisor's stated range is "C1260 to CB1700" — this is the heaviest series.
# ---------------------------------------------------------------------------
CB1700_CATALOG: list[CatalogEntry] = [
    #                           part_no          H      W    Kcomp  Kshear  dComp  dShear
    CatalogEntry("CB1700-15", 5.25, 5.50,  7565,  3890,  2.00,  2.00),
    CatalogEntry("CB1700-17", 6.00, 6.50,  5815,  2795,  2.40,  2.40),
    CatalogEntry("CB1700-20", 6.25, 7.00,  3695,  1775,  2.80,  2.80),
    CatalogEntry("CB1700-30", 7.50, 8.25,  1925,   900,  3.60,  3.60),
    CatalogEntry("CB1700-40", 8.50, 9.25,  1285,   545,  4.00,  4.00),
]

# Auto-select default — matches supervisor's stated range (CB1400 to CB1700).
# CB61400 excluded: ~25% softer than CB1400, produces 60–80 mm deflections at
# typical rack masses which is impractical for standard 19" rack installations.
AUTO_SELECT_CATALOGS: list[CatalogEntry] = (
    CB1400_CATALOG + CB1500_CATALOG + CB1700_CATALOG
)

# Full catalog — all four series including CB61400 (opt-in via UI)
ALL_CATALOGS: list[CatalogEntry] = (
    CB61400_CATALOG + CB1400_CATALOG + CB1500_CATALOG + CB1700_CATALOG
)


# ---------------------------------------------------------------------------
# Selection result
# ---------------------------------------------------------------------------

@dataclass
class CatalogCandidate:
    entry: CatalogEntry
    comp_bottom: DirectionResult   # Z-axis vertical    (K_comp, bottom mounts)
    comp_wall:   DirectionResult   # Y-axis lateral     (K_comp, wall mounts)
    roll_wall:   DirectionResult   # X,Z-axis shear     (K_shear, wall mounts)
    roll_bottom: DirectionResult   # X,Y-axis shear     (K_shear, bottom mounts)

    @property
    def valid(self) -> bool:
        return all(d.passed for d in self._dirs)

    @property
    def worst_GT_ratio(self) -> float:
        """Max GT/limit across all 4 cases. < 1.0 = pass."""
        return max(d.GT_G / d.GT_limit for d in self._dirs)

    @property
    def worst_delta_ratio(self) -> float:
        return max(d.delta_mm / d.delta_limit_mm for d in self._dirs)

    @property
    def worst_overall_ratio(self) -> float:
        """Worst of GT-ratio and deflection-ratio across all cases.
        Lower = more comfortably clear of *every* limit. Used by the
        'balanced' selection objective."""
        return max(self.worst_GT_ratio, self.worst_delta_ratio)

    @property
    def limiting_direction(self) -> DirectionResult:
        return max(self._dirs, key=lambda d: d.GT_G / d.GT_limit)

    @property
    def _dirs(self):
        return [self.comp_bottom, self.comp_wall, self.roll_wall, self.roll_bottom]


# ---------------------------------------------------------------------------
# Core selection
# ---------------------------------------------------------------------------

def select_isolator(
    m_comp_bottom_kg: float,
    m_comp_wall_kg: float,
    m_roll_wall_kg: float,
    m_roll_bottom_kg: float,
    env: ShockEnv,
    catalog: Optional[list[CatalogEntry]] = None,
    g: float = 9.81,
) -> list[CatalogCandidate]:
    """
    Evaluate every catalog entry against the FOUR load cases from the Excel reference.

    Args:
        m_comp_bottom_kg: Mass per bottom-mount in vertical compression  = M/n_bottom
        m_comp_wall_kg  : Mass per wall-mount   in lateral compression   = M/n_wall/2
        m_roll_wall_kg  : Mass per wall-mount   in shear/roll            = M/n_wall/2
        m_roll_bottom_kg: Mass per bottom-mount in shear/roll            = M/n_bottom/2
        env             : Shock environment (G, duration, GT limit)
        catalog         : Entries to scan (defaults to ALL_CATALOGS)

    Returns all candidates sorted: valid first, then by ascending K_comp (softest first).
    The first entry in the returned list is the RECOMMENDED part.

    Why softest first?
      Lower K -> lower fn -> lower GT (less shock transmitted).
      We want the best isolation that still keeps dD within the isolator's travel limit.
    """
    if catalog is None:
        catalog = ALL_CATALOGS

    candidates = []
    for entry in catalog:
        spec = entry.to_isolator_spec()
        comp_bottom = _calc_direction(
            "Comp - Bottom (Z-axis)",
            spec.k_comp_Nm,  m_comp_bottom_kg,  spec.d_max_comp_mm,  env, g,
        )
        comp_wall = _calc_direction(
            "Comp - Wall (Y-axis)",
            spec.k_comp_Nm,  m_comp_wall_kg,    spec.d_max_comp_mm,  env, g,
        )
        roll_wall = _calc_direction(
            "Roll - Wall (X,Z-axis)",
            spec.k_shear_Nm, m_roll_wall_kg,    spec.d_max_shear_mm, env, g,
        )
        roll_bottom = _calc_direction(
            "Roll - Bottom (X,Y-axis)",
            spec.k_shear_Nm, m_roll_bottom_kg,  spec.d_max_shear_mm, env, g,
        )
        candidates.append(CatalogCandidate(entry, comp_bottom, comp_wall, roll_wall, roll_bottom))

    # Sort: valid PASS entries first, then softest K (best isolation) as tiebreaker.
    candidates.sort(key=lambda c: (not c.valid, c.entry.k_comp_lbin))
    return candidates


def select_and_analyze(
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    cad_props: Optional[dict] = None,
    shock_env: Optional[ShockEnv] = None,
    catalog: Optional[list[CatalogEntry]] = None,
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
        m_comp_bottom_kg = loads["m_comp_bottom_kg"],
        m_comp_wall_kg   = loads["m_comp_wall_kg"],
        m_roll_wall_kg   = loads["m_roll_wall_kg"],
        m_roll_bottom_kg = loads["m_roll_bottom_kg"],
        env              = env,
        catalog          = catalog,
        g                = g,
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
    ASCII table: all catalog entries with computed GT for the 4 load cases
    (matches the 4 Excel sheets: Comp-Bottom, Comp-Wall, Roll-Wall, Roll-Bottom).
    """
    header = (
        f"{'Part':<14} {'Series':<8} {'Kcomp':>7} {'Kshear':>7} | "
        f"{'C-Bot GT':>8} | {'C-Wal GT':>8} | {'R-Wal GT':>8} | {'R-Bot GT':>8} | "
        f"{'maxGT':>6} {'STATUS':>6}"
    )
    sep = "-" * len(header)

    env_str = "20G / 11ms saw-tooth"
    lines = [
        "=" * len(header),
        f"MULTI-SERIES SELECTION MATRIX ({env_str}) — 4 load cases per Excel",
        f"{'':14} {'':8} {'lb/in':>7} {'lb/in':>7} | "
        f"{'[G]':>8} | {'[G]':>8} | {'[G]':>8} | {'[G]':>8} | "
        f"{'[G]':>6}",
        header,
        sep,
    ]

    for c in candidates:
        cb, cw, rw, rb = c.comp_bottom, c.comp_wall, c.roll_wall, c.roll_bottom
        worst = max(cb.GT_G, cw.GT_G, rw.GT_G, rb.GT_G)
        status = "PASS" if c.valid else "FAIL"
        lines.append(
            f"{c.entry.part_no:<14} "
            f"{c.entry.series:<8} "
            f"{c.entry.k_comp_lbin:>7.0f} "
            f"{c.entry.k_shear_lbin:>7.0f} | "
            f"{cb.GT_G:>8.3f} | {cw.GT_G:>8.3f} | {rw.GT_G:>8.3f} | {rb.GT_G:>8.3f} | "
            f"{worst:>6.2f} {status:>6}"
        )
    lines.append("=" * len(header))

    valid_list = [c for c in candidates if c.valid]
    if valid_list:
        rec = valid_list[0]
        lines.append(
            f"\nRECOMMENDED: {rec.entry.part_no}  ({rec.entry.series}, "
            f"H={rec.entry.H_in}\" x W={rec.entry.W_in}\" | "
            f"worst GT ratio: {rec.worst_GT_ratio:.0%} of limit)"
        )
        lines.append(_math_proof(rec))
    else:
        lines.append("\nNO VALID PART FOUND. Options: increase n_mounts OR relax GT_limit OR change shock profile.")

    return "\n".join(lines)


def _math_proof(c: CatalogCandidate) -> str:
    e = c.entry
    lines = [
        f"\nMATHEMATICAL PROOF — {e.part_no}  [{e.series}]",
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
    Compact summary injected into LLM context so the AI explains
    the recommendation rather than inventing its own numbers.
    """
    valid = [c for c in candidates if c.valid]
    fail  = [c for c in candidates if not c.valid]
    rec   = valid[0] if valid else None

    parts = ["=== CATALOG SELECTION RESULTS ==="]
    if rec:
        d = rec.limiting_direction
        parts.append(
            f"RECOMMENDED PART: {rec.entry.part_no}  (Series: {rec.entry.series})\n"
            f"  K_comp = {rec.entry.k_comp_lbin} lb/in | K_shear = {rec.entry.k_shear_lbin} lb/in\n"
            f"  Physical size: H={rec.entry.H_in}\" x W={rec.entry.W_in}\"\n"
            f"  Limiting direction: {d.label}\n"
            f"    fn={d.fn_Hz:.2f} Hz | GT={d.GT_G:.2f} G (limit {d.GT_limit} G) | "
            f"dD={d.delta_mm:.1f} mm (limit {d.delta_limit_mm:.1f} mm)"
        )
        if len(valid) > 1:
            parts.append("  Also valid (softer alternatives): " +
                         ", ".join(c.entry.part_no for c in valid[1:]))
        else:
            parts.append("  No softer alternative passes.")
    else:
        parts.append("NO VALID PART FOUND in any catalog series for this load/shock combination.")
    parts.append("Parts that FAIL: " + ", ".join(c.entry.part_no for c in fail))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point — extracts mass from live SolidWorks CAD, then selects
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from cad_compliance_checker import extract_cad_data

    # --- Mount configuration (edit to match your assembly) ---
    N_BOTTOM = 6
    N_WALL   = 4
    ENV      = ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0)

    # --- Pull mass (and CG/envelope) from SolidWorks ---
    print("Extracting CAD data from SolidWorks...")
    cad_props = extract_cad_data()

    if not cad_props or not cad_props.get("mass_kg"):
        print("WARNING: Could not extract CAD data. Using fallback mass = 850 kg.")
        mass_kg   = 850.0
        cad_props = {"mass_kg": mass_kg}
    else:
        mass_kg = cad_props["mass_kg"]
        print(f"  Mass from CAD     : {mass_kg:.2f} kg")
        print(f"  Envelope          : W={cad_props.get('width_mm','?')} "
              f"D={cad_props.get('depth_mm','?')} "
              f"H={cad_props.get('height_mm','?')} mm")
        print(f"  CG (raw, default) : X={cad_props.get('cg_x','?')}, "
              f"Y={cad_props.get('cg_y','?')}, Z={cad_props.get('cg_z','?')} mm")
        if cad_props.get("cg_z_base") is not None:
            print(f"  CG from Base      : X={cad_props['cg_x_base']:.2f}, "
                  f"Y={cad_props['cg_y_base']:.2f}, Z={cad_props['cg_z_base']:.2f} mm")
            if cad_props.get("height_mm"):
                ratio = cad_props['cg_z_base'] / cad_props['height_mm']
                print(f"  CG Height Ratio   : {ratio*100:.1f}% of rack height")

    # --- Run selection across all series ---
    # CG/envelope from SolidWorks coordinates are not yet calibrated —
    # pass only mass to the physics engine until coordinate origin is resolved.
    print(f"\nRunning selection for {mass_kg:.1f} kg, "
          f"{N_BOTTOM} bottom + {N_WALL} wall mounts ...\n")

    report, candidates = select_and_analyze(
        mass_kg=mass_kg,
        n_bottom=N_BOTTOM,
        n_wall=N_WALL,
        cad_props=cad_props,   # now contains cg_z_base — high-CG warning is meaningful
        shock_env=ENV,
    )
    print(format_selection_table(candidates))
    print()
    print(format_report(report))
