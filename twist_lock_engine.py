"""
ISO twist-lock strength check.
Transcribed from: T1 Measured CG_23-10-2025.xlsx sheets
'StrengthChk_TwistLock(Measured)' and '(Theory)'.
Validated: scripts/validate_t1_twistlock.py reproduces all six stored rows.

An ISO shelter is locked to the transporter sub-frame by N twist-locks
(4 for a 20-ft shelter). During transport each direction sees an inertia
load; the total is shared equally by the locks:

    F_total_axis  = W_shelter * G_axis * g          [N]
    F_per_lock    = F_total_axis / n_locks          [N]
    SF_axis       = allowable_axis / F_per_lock
    PASS if F_per_lock < allowable_axis

Design loads (OEM, per the T-1 SAR 4.2): 4G longitudinal, 1.5G lateral,
2G vertical. Allowable force per lock (OEM): 170 kN longitudinal and
lateral, 85 kN vertical.

This mirrors the tie-down engine's force-balance pattern but with a fixed
per-lock allowable table instead of a fastener-capacity model.
"""
from dataclasses import dataclass, field
from typing import Optional

G_STD = 9.81  # m/s^2

# OEM design load factors (multiples of shelter weight), per axis.
DESIGN_G = {
    "longitudinal": 4.0,
    "lateral": 1.5,
    "vertical": 2.0,
}

# OEM allowable force per twist-lock [N], per axis.
ALLOWABLE_N = {
    "longitudinal": 170_000.0,
    "lateral": 170_000.0,
    "vertical": 85_000.0,
}

AXES = ("longitudinal", "lateral", "vertical")


@dataclass(frozen=True)
class TwistLockAxis:
    axis: str
    load_factor: float          # G multiple
    design_force_N: float       # W * G * g (total across all locks)
    force_per_lock_N: float     # design_force / n_locks
    allowable_N: float
    SF: float

    @property
    def passed(self) -> bool:
        return self.force_per_lock_N < self.allowable_N


@dataclass
class TwistLockReport:
    shelter_weight_kg: float
    n_locks: int
    axes: list = field(default_factory=list)   # list[TwistLockAxis], order = AXES

    @property
    def all_passed(self) -> bool:
        return all(a.passed for a in self.axes)

    @property
    def min_SF(self) -> float:
        return min(a.SF for a in self.axes)

    def by_axis(self, axis: str) -> TwistLockAxis:
        return next(a for a in self.axes if a.axis == axis)


def analyze_twist_locks(
    shelter_weight_kg: float,
    n_locks: int = 4,
    g: float = G_STD,
    design_g: Optional[dict] = None,
    allowable_N: Optional[dict] = None,
) -> TwistLockReport:
    """
    ISO twist-lock strength check for a laden shelter.

    Args:
        shelter_weight_kg : laden shelter (payload) weight in kg.
        n_locks           : number of twist-locks sharing the load (4 for 20-ft).
        design_g          : {axis: G} override (default OEM 4 / 1.5 / 2).
        allowable_N       : {axis: N} per-lock allowable override
                            (default OEM 170k / 170k / 85k).
    """
    if shelter_weight_kg <= 0:
        raise ValueError("shelter_weight_kg must be positive")
    if n_locks <= 0:
        raise ValueError("n_locks must be a positive integer")

    dg = design_g or DESIGN_G
    al = allowable_N or ALLOWABLE_N

    axes = []
    for axis in AXES:
        Gfac = dg[axis]
        F_total = shelter_weight_kg * Gfac * g
        F_per = F_total / n_locks
        allow = al[axis]
        axes.append(TwistLockAxis(
            axis=axis, load_factor=Gfac,
            design_force_N=F_total, force_per_lock_N=F_per,
            allowable_N=allow, SF=allow / F_per,
        ))
    return TwistLockReport(shelter_weight_kg, n_locks, axes)


def format_twist_lock_report(report: TwistLockReport) -> str:
    lines = [
        "=" * 68,
        "ISO TWIST-LOCK STRENGTH CHECK",
        f"  Shelter weight : {report.shelter_weight_kg:,.1f} kg",
        f"  Twist-locks    : {report.n_locks}",
        "=" * 68,
        f"  {'Axis':<13}{'G':>4}{'Total (N)':>14}{'Per-lock (N)':>15}"
        f"{'Allow (N)':>12}{'SF':>7}  Verdict",
        "-" * 68,
    ]
    for a in report.axes:
        verdict = "PASS" if a.passed else "FAIL"
        lines.append(
            f"  {a.axis:<13}{a.load_factor:>4.1f}{a.design_force_N:>14,.1f}"
            f"{a.force_per_lock_N:>15,.1f}{a.allowable_N:>12,.0f}{a.SF:>7.2f}  {verdict}"
        )
    lines.append("-" * 68)
    lines.append("Overall: " + ("ALL PASS" if report.all_passed
                                 else f"FAIL (min SF {report.min_SF:.2f})"))
    lines.append("=" * 68)
    return "\n".join(lines)


if __name__ == "__main__":
    # Measured T-1 shelter (9405 kg)
    rep = analyze_twist_locks(9405.0)
    print(format_twist_lock_report(rep))
    assert abs(rep.by_axis("longitudinal").force_per_lock_N - 92263.05) < 1e-6
    print("\n[OK] longitudinal per-lock force matches T-1 workbook (92263.05 N)")
