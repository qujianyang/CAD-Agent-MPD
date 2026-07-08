"""
Run the validated shock engine against a normalized custom isolator.

The normalization layer owns vendor data conversion; this layer owns the
single-part analysis result shape that future UI/agent tools can consume.
"""
from dataclasses import dataclass
from typing import Optional

from custom_isolator import (
    CustomIsolatorInput,
    NormalizedCustomIsolator,
    ValidationError,
    normalize_custom_isolator,
)
from physics_engine import PhysicsReport, ShockEnv, _NO_CLEARANCE_MM, run_analysis


@dataclass(frozen=True)
class CustomIsolatorAnalysis:
    normalized: NormalizedCustomIsolator
    report: PhysicsReport
    static_load_daN: float
    static_rating_daN: Optional[float]

    @property
    def validation_level(self) -> str:
        return self.normalized.validation_level

    @property
    def static_ok(self) -> Optional[bool]:
        if self.static_rating_daN is None:
            return None
        return self.static_load_daN <= self.static_rating_daN

    @property
    def passed(self) -> bool:
        return self.report.all_passed and self.static_ok is not False

    @property
    def verdict(self) -> str:
        return "PASS" if self.passed else "FAIL"

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.normalized.warnings + tuple(self.report.warnings)


def analyze_custom_isolator(
    raw: CustomIsolatorInput,
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    cad_props: Optional[dict] = None,
    shock_env: Optional[ShockEnv] = None,
    g: float = 9.81,
    clr_x_mm: float = _NO_CLEARANCE_MM,
    clr_y_mm: float = _NO_CLEARANCE_MM,
    clr_z_mm: float = _NO_CLEARANCE_MM,
) -> CustomIsolatorAnalysis:
    """Normalize a custom part and run the existing four-case shock analysis."""
    _require_positive(mass_kg, "mass_kg")
    _require_positive_int(n_bottom, "n_bottom")
    _require_positive_int(n_wall, "n_wall")

    normalized = normalize_custom_isolator(raw)
    report = run_analysis(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        cad_props=cad_props,
        shock_env=shock_env,
        isolator=normalized.spec,
        g=g,
        clr_x_mm=clr_x_mm,
        clr_y_mm=clr_y_mm,
        clr_z_mm=clr_z_mm,
    )
    static_load_daN = (mass_kg / n_bottom) * g / 10.0
    return CustomIsolatorAnalysis(
        normalized=normalized,
        report=report,
        static_load_daN=static_load_daN,
        static_rating_daN=normalized.spec.max_static_comp_daN,
    )


def _require_positive(value: float, field_name: str) -> None:
    if value is None or value <= 0:
        raise ValidationError(f"{field_name} must be > 0")


def _require_positive_int(value: int, field_name: str) -> None:
    if value is None or value <= 0:
        raise ValidationError(f"{field_name} must be > 0")
