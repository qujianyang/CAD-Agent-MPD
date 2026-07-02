"""
Random-vibration engine for isolator mounts.
Method transcribed from: SPF_Vibration.xls (company workbook).
Validated: scripts/validate_vibration_excel.py reproduces the workbook's
transmissibility column, output PSD and both g_rms values.

Chain:  input PSD (chassis)  ->  T(f) damped transmissibility  ->
        PSD_out = T^2 * PSD_in  ->  g_rms = sqrt(area under PSD)

Notes on fidelity to the workbook:
- T(f) is the standard damped single-DOF form with zeta = 0.12 (wire-rope
  friction damping, the workbook's value).
- Integration is RIGHT-ENDPOINT rectangles (area_i = PSD_i * (f_i - f_{i-1})),
  exactly as the workbook computes its Area columns. Slightly cruder than
  trapezoidal, kept for validation parity.
- The natural frequency used is the DAMPED one, fd = fn*sqrt(1-zeta^2) —
  reconciles the workbook's fn cell (27.106 Hz vs undamped 27.31 Hz).

Why this module exists: shock selection prefers the SOFTEST passing mount,
which pushes fn toward the chassis suspension band. The truck PSD peaks at
3.6-4.3 Hz (0.23-0.25 G^2/Hz); a mount whose vibration-K natural frequency
lands there rides its own resonance (Q ~ 1/(2*zeta) ~ 4) all day. The
vendor publishes a separate "Vibration Average K" (2-3x the shock K,
amplitude-dependent stiffness) — that is the stiffness used here.
"""
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Input PSD — "Fig. 11 Chassis Vibration Data, Vertical Rear Frame,
# Heavy-Duty Truck" as tabulated in SPF_Vibration.xls (Sheet1 B6:C33).
# (frequency [Hz], acceleration PSD [G^2/Hz])
# ---------------------------------------------------------------------------
CHASSIS_PSD_TRUCK: Tuple[Tuple[float, float], ...] = (
    (1.0, 0.012), (1.5, 0.0115), (2.0, 0.02), (3.0, 0.03),
    (3.6, 0.23), (4.0, 0.25), (4.3, 0.24), (5.0, 0.02),
    (6.3, 0.17), (7.0, 0.23), (8.0, 0.17), (9.0, 0.07),
    (10.0, 0.1), (20.0, 0.024), (70.0, 0.0115), (80.0, 0.0115),
    (84.0, 0.013), (90.0, 0.0115), (100.0, 0.01), (200.0, 0.01),
    (300.0, 0.028), (340.0, 0.1), (400.0, 0.02), (430.0, 0.04),
    (500.0, 0.0115), (530.0, 0.03), (600.0, 0.0115), (650.0, 0.0115),
)

DEFAULT_ZETA = 0.12   # wire-rope equivalent viscous damping (SPF workbook)


def transmissibility(f_Hz: float, fn_Hz: float, zeta: float = DEFAULT_ZETA) -> float:
    """
    Damped single-DOF transmissibility:
        T = sqrt( (1 + (2*zeta*r)^2) / ((1 - r^2)^2 + (2*zeta*r)^2) ),  r = f/fn
    T > 1 below f = fn*sqrt(2) (amplification), T < 1 above (isolation).
    """
    r = f_Hz / fn_Hz
    num = 1.0 + (2.0 * zeta * r) ** 2
    den = (1.0 - r * r) ** 2 + (2.0 * zeta * r) ** 2
    return math.sqrt(num / den)


def grms_right_rect(psd_pts: Sequence[Tuple[float, float]]) -> float:
    """
    g_rms = sqrt(area under the PSD), integrated with RIGHT-ENDPOINT
    rectangles (area_i = PSD_i * (f_i - f_{i-1}); first point contributes 0).
    Replicates the SPF workbook's Area column exactly.
    """
    area = 0.0
    for i in range(1, len(psd_pts)):
        df = psd_pts[i][0] - psd_pts[i - 1][0]
        area += psd_pts[i][1] * df
    return math.sqrt(area)


@dataclass
class VibrationResult:
    m_kg: float
    k_vib_Nm: float
    zeta: float
    fn_Hz: float                 # damped natural frequency fd = fn*sqrt(1-zeta^2)
    grms_in: float
    grms_out: float
    resonance_flag: bool         # fn sits where the input PSD is near its peak
    rows: list = field(default_factory=list)   # (f, PSD_in, T, PSD_out)

    @property
    def attenuation(self) -> float:
        """grms_out / grms_in — < 1 means net isolation over the full band."""
        return self.grms_out / self.grms_in if self.grms_in > 0 else float("nan")


def run_vibration_analysis(
    m_kg: float,
    k_vib_Nm: float,
    zeta: float = DEFAULT_ZETA,
    psd: Sequence[Tuple[float, float]] = CHASSIS_PSD_TRUCK,
    resonance_band_fraction: float = 0.5,
) -> VibrationResult:
    """
    Random-vibration response of a mount (mass per isolator m, vibration
    stiffness k_vib) to the input PSD.

    resonance_flag: True when the mount's fn falls at a frequency where the
    input PSD is >= resonance_band_fraction * max(PSD) — i.e. the mount
    resonates on a dominant excitation band (interpolated linearly between
    breakpoints).
    """
    if m_kg <= 0 or k_vib_Nm <= 0:
        raise ValueError("m_kg and k_vib_Nm must be positive")

    fn_undamped = math.sqrt(k_vib_Nm / m_kg) / (2.0 * math.pi)
    fn = fn_undamped * math.sqrt(1.0 - zeta * zeta)   # damped, as per workbook

    rows = []
    out_pts = []
    for f, p_in in psd:
        T = transmissibility(f, fn, zeta)
        p_out = T * T * p_in
        rows.append((f, p_in, T, p_out))
        out_pts.append((f, p_out))

    grms_in = grms_right_rect(psd)
    grms_out = grms_right_rect(out_pts)

    # PSD level at fn (linear interpolation), vs the table peak
    peak = max(p for _, p in psd)
    p_at_fn = 0.0
    if psd[0][0] <= fn <= psd[-1][0]:
        for i in range(1, len(psd)):
            f0, p0 = psd[i - 1]
            f1, p1 = psd[i]
            if f0 <= fn <= f1:
                w = 0.0 if f1 == f0 else (fn - f0) / (f1 - f0)
                p_at_fn = p0 + w * (p1 - p0)
                break
    resonance_flag = p_at_fn >= resonance_band_fraction * peak

    return VibrationResult(
        m_kg=m_kg, k_vib_Nm=k_vib_Nm, zeta=zeta, fn_Hz=fn,
        grms_in=grms_in, grms_out=grms_out,
        resonance_flag=resonance_flag, rows=rows,
    )


def vibration_check_for_entry(entry, m_comp_bottom_kg: float,
                              zeta: float = DEFAULT_ZETA,
                              psd: Sequence[Tuple[float, float]] = CHASSIS_PSD_TRUCK,
                              ) -> Optional[VibrationResult]:
    """
    Vertical road-vibration check for a catalog part: uses the vendor's
    "Vibration Average K" in compression and the per-bottom-mount mass.
    Returns None when the entry has no published vibration K.
    """
    k_vib = entry.k_vib_comp_Nm
    if k_vib is None:
        return None
    return run_vibration_analysis(m_comp_bottom_kg, k_vib, zeta=zeta, psd=psd)


def format_vibration_report(res: VibrationResult) -> str:
    verdict = ("RESONANCE RISK — fn sits on a dominant band of the input PSD"
               if res.resonance_flag else
               ("net isolation" if res.attenuation < 1.0 else "net amplification"))
    lines = [
        "=" * 64,
        "ROAD-VIBRATION CHECK (chassis PSD, heavy-duty truck)",
        f"  m/mount   : {res.m_kg:.1f} kg    K_vib: {res.k_vib_Nm:,.0f} N/m    "
        f"zeta: {res.zeta}",
        f"  fn (damped): {res.fn_Hz:.2f} Hz",
        f"  g_rms in  : {res.grms_in:.3f} g",
        f"  g_rms out : {res.grms_out:.3f} g   (x{res.attenuation:.2f})",
        f"  Verdict   : {verdict}",
        "=" * 64,
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    # SPF workbook's own system: K = ILoad*g/IDeflection = 4.5*9.81/0.0015
    res = run_vibration_analysis(m_kg=1.0, k_vib_Nm=29430.0)
    print(format_vibration_report(res))
    assert abs(res.grms_in - 3.9405266145529327) < 1e-9
    print("\n[OK] grms_in matches SPF workbook (3.9405)")
