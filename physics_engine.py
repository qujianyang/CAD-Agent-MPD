"""
Shock isolation physics engine.
Formulas transcribed from: Shock Isolator_850kg_4 Bayed 35U.xls
Pulse type: Saw-Tooth acceleration profile.
"""
import math
from dataclasses import dataclass, field
from typing import Optional

# Sentinel "no clearance constraint" — large enough that min(d_max, this) == d_max,
# so leaving clearance unset reproduces the original (travel-limited) behaviour.
_NO_CLEARANCE_MM = 1.0e9


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IsolatorSpec:
    name: str
    k_comp_Nm: float      # Compression stiffness [N/m]
    k_shear_Nm: float     # Shear/roll stiffness [N/m]
    d_max_comp_mm: float  # Max deflection, compression [mm]
    d_max_shear_mm: float # Max deflection, shear [mm]


@dataclass
class ShockEnv:
    Ao_G: float = 20.0    # Shock magnitude [G]
    to_s: float = 0.011   # Shock pulse duration [s]  (saw-tooth)
    GT_limit_G: float = 10.0  # Max allowable transmitted G
    pulse_shape: str = "sawtooth"  # "sawtooth" (V=0.5*g*Ao*to) or "half_sine" (V=(2/pi)*g*Ao*to)


@dataclass
class DirectionResult:
    label: str            # e.g. "Compression — Z (vertical)"
    k_Nm: float
    m_kg: float           # Load per isolator
    V_ms: float           # Velocity change [m/s]
    fn_Hz: float          # Natural frequency [Hz]
    GT_G: float           # Transmitted G
    delta_mm: float       # Dynamic deflection [mm]
    GT_limit: float
    delta_limit_mm: float

    @property
    def GT_ok(self) -> bool:
        return self.GT_G < self.GT_limit

    @property
    def delta_ok(self) -> bool:
        return self.delta_mm < self.delta_limit_mm

    @property
    def passed(self) -> bool:
        return self.GT_ok and self.delta_ok


@dataclass
class PhysicsReport:
    mass_kg: float
    n_bottom: int
    n_wall: int
    isolator: IsolatorSpec
    shock_env: ShockEnv
    directions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(d.passed for d in self.directions)


# ---------------------------------------------------------------------------
# Catalog — add more isolators here as you source new parts
# ---------------------------------------------------------------------------

CB1400_15 = IsolatorSpec(
    name="CB1400-15",
    k_comp_Nm=464_086.126,  # 2650 lb/in
    k_shear_Nm=189_136.987, # 1080 lb/in
    d_max_comp_mm=35.56,    # 1.4 in
    d_max_shear_mm=40.64,   # 1.6 in
)

DEFAULT_ISOLATOR = CB1400_15


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

# Velocity-change coefficient by pulse profile.  V = coeff * g * Ao * to
# Saw-tooth (terminal-peak) integrates to 1/2 of the peak; a half-sine pulse
# integrates to 2/pi (~0.637), i.e. ~27% harsher for the same Ao/to.
_PULSE_COEFF = {
    "sawtooth":  0.5,
    "half_sine": 2.0 / math.pi,
}


def _velocity_change(g: float, Ao_G: float, to_s: float, pulse_shape: str = "sawtooth") -> float:
    """V = coeff * g * Ao * to, where coeff depends on the pulse profile."""
    coeff = _PULSE_COEFF.get(pulse_shape, 0.5)
    return coeff * g * Ao_G * to_s


def _natural_freq(k_Nm: float, m_kg: float) -> float:
    """fn = (1 / 2π) * sqrt(k / m)"""
    return (1.0 / (2.0 * math.pi)) * math.sqrt(k_Nm / m_kg)


def _transmitted_g(fn_Hz: float, V_ms: float, g: float) -> float:
    """GT = (2π * fn * V) / g"""
    return (2.0 * math.pi * fn_Hz * V_ms) / g


def _dynamic_deflection_mm(V_ms: float, fn_Hz: float) -> float:
    """ΔD = V / (2π * fn)  →  converted to mm"""
    return (V_ms / (2.0 * math.pi * fn_Hz)) * 1000.0


def _calc_direction(
    label: str,
    k_Nm: float,
    m_kg: float,
    d_max_mm: float,
    env: ShockEnv,
    g: float = 9.81,
) -> DirectionResult:
    V  = _velocity_change(g, env.Ao_G, env.to_s, env.pulse_shape)
    fn = _natural_freq(k_Nm, m_kg)
    GT = _transmitted_g(fn, V, g)
    dD = _dynamic_deflection_mm(V, fn)
    return DirectionResult(
        label=label, k_Nm=k_Nm, m_kg=m_kg,
        V_ms=V, fn_Hz=fn, GT_G=GT, delta_mm=dD,
        GT_limit=env.GT_limit_G, delta_limit_mm=d_max_mm,
    )


# ---------------------------------------------------------------------------
# Load distribution
# ---------------------------------------------------------------------------

def _loads_per_isolator(
    mass_kg: float,
    n_bottom: int,
    n_wall: int,
) -> dict:
    """
    Returns effective mass per isolator for each of the FOUR analysis cases.
    Formulas transcribed verbatim from "Shock Isolator_850kg_4 Bayed 35U.xls":

      | Case            | Direction | Excel formula        | Physical reasoning                           |
      |-----------------|-----------|----------------------|----------------------------------------------|
      | Comp - Bottom   | Z         | M / n_bottom         | Gravity is unidirectional; all bottom mounts |
      |                 |           |                      | share the weight equally.                    |
      | Comp - Wall     | Y         | M / n_wall   / 2     | Lateral Y shock: two opposing wall faces     |
      |                 |           |                      | share the load (load-sharing factor 1/2).    |
      | Roll - Wall     | X, Z      | M / n_wall   / 2     | Same load-sharing logic; shear stiffness.    |
      | Roll - Bottom   | X, Y      | M / n_bottom / 2     | Same load-sharing logic; bottom mounts in    |
      |                 |           |                      | shear.                                       |

    Validated against 850kg/CB1400-15 reference sheet — see __main__ smoke test.
    """
    if n_bottom <= 0 or n_wall <= 0:
        raise ValueError("n_bottom and n_wall must both be > 0")

    return {
        # Z-axis vertical: all bottom mounts share gravity equally
        "m_comp_bottom_kg":  mass_kg / n_bottom,
        # Y-axis lateral compression on wall mounts (load-sharing 1/2)
        "m_comp_wall_kg":    mass_kg / n_wall   / 2.0,
        # X,Z-axis shear/roll on wall mounts (load-sharing 1/2)
        "m_roll_wall_kg":    mass_kg / n_wall   / 2.0,
        # X,Y-axis shear/roll on bottom mounts (load-sharing 1/2)
        "m_roll_bottom_kg":  mass_kg / n_bottom / 2.0,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis(
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    cad_props: Optional[dict] = None,
    shock_env: Optional[ShockEnv] = None,
    isolator: Optional[IsolatorSpec] = None,
    g: float = 9.81,
    clr_x_mm: float = _NO_CLEARANCE_MM,
    clr_y_mm: float = _NO_CLEARANCE_MM,
    clr_z_mm: float = _NO_CLEARANCE_MM,
) -> PhysicsReport:
    """
    Full shock isolation analysis.

    Args:
        mass_kg:    Total system mass from CAD.
        n_bottom:   Number of bottom-mounted isolators.
        n_wall:     Number of wall-mounted isolators.
        cad_props:  Full CAD dict (used for CG, dimensions, warnings).
        shock_env:  Shock environment (defaults to 20G, 11ms saw-tooth).
        isolator:   Isolator specification (defaults to CB1400-15).
        clr_*_mm:   Installation clearance per axis [mm]. The effective deflection
                    limit per case is min(mount travel, mapped clearance) — see
                    catalog.select_isolator for the axis->case mapping. Defaults to
                    "unlimited" so behaviour is unchanged when clearance is unset.
    """
    env  = shock_env or ShockEnv()
    spec = isolator  or DEFAULT_ISOLATOR

    # Extract optional geometry from CAD (for warnings only — load distribution
    # follows the Excel reference and does NOT use CG/footprint corrections).
    # Prefer the base-relative CG (cg_z_base) — this is the actual CG height
    # above the mounting floor and is what the high-CG/overturn warning needs.
    # Falls back to cg_z (default origin frame) only if base-relative is missing.
    cg_z = 0.0
    height_mm = 0.0
    if cad_props:
        cg_z = (
            cad_props.get("cg_z_base")
            if cad_props.get("cg_z_base") is not None
            else (cad_props.get("cg_z", 0.0) or 0.0)
        )
        height_mm = cad_props.get("height_mm", 0.0) or 0.0

    loads = _loads_per_isolator(mass_kg, n_bottom, n_wall)

    # Effective deflection limit per case = min(mount travel, mapped clearance).
    # Axis->case mapping per the Excel direction sheets (Z=Comp-Bottom, Y=Comp-Wall,
    # X&Z=Roll-Wall, X&Y=Roll-Bottom).
    lim_comp_bottom = min(spec.d_max_comp_mm,  clr_z_mm)
    lim_comp_wall   = min(spec.d_max_comp_mm,  clr_y_mm)
    lim_roll_wall   = min(spec.d_max_shear_mm, clr_x_mm, clr_z_mm)
    lim_roll_bottom = min(spec.d_max_shear_mm, clr_x_mm, clr_y_mm)

    # 4 load cases — exactly matches the 4 Excel sheets.
    directions = [
        _calc_direction(
            "Comp - Bottom (Z-axis, vertical)",
            spec.k_comp_Nm,  loads["m_comp_bottom_kg"],
            lim_comp_bottom,  env, g,
        ),
        _calc_direction(
            "Comp - Wall (Y-axis, lateral)",
            spec.k_comp_Nm,  loads["m_comp_wall_kg"],
            lim_comp_wall,  env, g,
        ),
        _calc_direction(
            "Roll - Wall (X,Z-axis, shear)",
            spec.k_shear_Nm, loads["m_roll_wall_kg"],
            lim_roll_wall, env, g,
        ),
        _calc_direction(
            "Roll - Bottom (X,Y-axis, shear)",
            spec.k_shear_Nm, loads["m_roll_bottom_kg"],
            lim_roll_bottom, env, g,
        ),
    ]

    # --- Warnings ---
    warnings = []

    # CG height: overturning risk if CG > 60 % of height
    if height_mm > 0 and cg_z > 0:
        ratio = cg_z / height_mm
        if ratio > 0.6:
            warnings.append(
                f"High CG: CG is at {cg_z:.0f} mm ({ratio*100:.0f}% of height {height_mm:.0f} mm). "
                "Consider vertical stabiliser bars or reduced top-heavy loading."
            )

    # GT failure
    for d in directions:
        if not d.GT_ok:
            warnings.append(
                f"FAIL [{d.label}]: GT = {d.GT_G:.2f} G exceeds limit {d.GT_limit} G."
            )
        if not d.delta_ok:
            warnings.append(
                f"FAIL [{d.label}]: ΔD = {d.delta_mm:.1f} mm exceeds limit {d.delta_limit_mm} mm."
            )

    return PhysicsReport(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        isolator=spec,
        shock_env=env,
        directions=directions,
        warnings=warnings,
    )


def format_report(report: PhysicsReport) -> str:
    """Human-readable report string for CLI or LLM context injection."""
    lines = [
        "=" * 60,
        "SHOCK ISOLATION PHYSICS ANALYSIS",
        f"  Isolator    : {report.isolator.name}",
        f"  System Mass : {report.mass_kg:.1f} kg",
        f"  Mounts      : {report.n_bottom} bottom + {report.n_wall} wall",
        f"  Shock Env   : {report.shock_env.Ao_G} G, {report.shock_env.to_s*1000:.0f} ms ({report.shock_env.pulse_shape})",
        "=" * 60,
    ]
    for d in report.directions:
        status = "PASS" if d.passed else "FAIL"
        lines += [
            f"\n[{status}] {d.label}",
            f"  Load/isolator : {d.m_kg:.2f} kg",
            f"  k             : {d.k_Nm:,.0f} N/m",
            f"  V             : {d.V_ms:.4f} m/s",
            f"  fn            : {d.fn_Hz:.3f} Hz",
            f"  GT            : {d.GT_G:.3f} G  (limit: {d.GT_limit} G)  {'OK' if d.GT_ok else 'FAIL'}",
            f"  dD            : {d.delta_mm:.2f} mm  (limit: {d.delta_limit_mm} mm)  {'OK' if d.delta_ok else 'FAIL'}",
        ]
    if report.warnings:
        lines += ["", "WARNINGS:"]
        for w in report.warnings:
            lines.append(f"  ⚠  {w}")
    lines += ["", "Overall: " + ("ALL PASS" if report.all_passed else "ONE OR MORE FAILURES")]
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quick smoke-test (matches Excel values)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    report = run_analysis(
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        shock_env=ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0),
    )
    print(format_report(report))
