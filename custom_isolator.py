"""
Vendor-neutral custom isolator normalization.

This module converts vendor/user-supplied catalog data into the IsolatorSpec
shape consumed by the validated shock engine. It does not run physics.
"""
import math
from dataclasses import dataclass
from typing import Optional

from physics_engine import IsolatorSpec


_LB_IN_TO_N_M = 175.1268
_N_MM_TO_N_M = 1000.0
_IN_TO_MM = 25.4
_KG_TO_DAN = 0.981


class ValidationError(ValueError):
    """Raised when vendor data is missing or cannot be safely normalized."""


@dataclass(frozen=True)
class StiffnessInput:
    method: str
    value: float
    unit: str
    frequency_hz: Optional[float] = None
    deflection: Optional[float] = None
    deflection_unit: Optional[str] = None

    @classmethod
    def direct_k(cls, value: float, unit: str) -> "StiffnessInput":
        return cls(method="direct_k", value=value, unit=unit)

    @classmethod
    def rated_load_frequency(
        cls,
        rated_load: float,
        load_unit: str,
        frequency_hz: float,
    ) -> "StiffnessInput":
        if frequency_hz <= 0:
            raise ValidationError("frequency_hz must be > 0")
        return cls(
            method="rated_load_frequency",
            value=rated_load,
            unit=load_unit,
            frequency_hz=frequency_hz,
        )

    @classmethod
    def force_deflection(
        cls,
        force: float,
        force_unit: str,
        deflection: float,
        deflection_unit: str,
    ) -> "StiffnessInput":
        return cls(
            method="force_deflection",
            value=force,
            unit=force_unit,
            deflection=deflection,
            deflection_unit=deflection_unit,
        )


@dataclass(frozen=True)
class DirectionInput:
    stiffness: StiffnessInput
    max_dynamic_travel: float
    travel_unit: str


@dataclass(frozen=True)
class CustomIsolatorInput:
    vendor: str
    part_no: str
    compression: Optional[DirectionInput]
    shear: Optional[DirectionInput]
    max_static_comp: Optional[float] = None
    max_static_comp_unit: Optional[str] = None
    source: str = ""


@dataclass(frozen=True)
class NormalizedCustomIsolator:
    spec: IsolatorSpec
    vendor: str
    part_no: str
    source: str
    stiffness_source_comp: str
    stiffness_source_shear: str
    validation_level: str
    warnings: tuple[str, ...] = ()


def normalize_custom_isolator(raw: CustomIsolatorInput) -> NormalizedCustomIsolator:
    """Validate and normalize custom vendor data into an IsolatorSpec."""
    vendor = _required_text(raw.vendor, "vendor")
    part_no = _required_text(raw.part_no, "part_no")
    if raw.compression is None:
        raise ValidationError("compression data is required")
    if raw.shear is None:
        raise ValidationError("shear data is required")

    k_comp_Nm, comp_source = _stiffness_to_Nm(raw.compression.stiffness)
    k_shear_Nm, shear_source = _stiffness_to_Nm(raw.shear.stiffness)
    d_max_comp_mm = _length_to_mm(
        raw.compression.max_dynamic_travel,
        raw.compression.travel_unit,
        "compression max dynamic travel",
    )
    d_max_shear_mm = _length_to_mm(
        raw.shear.max_dynamic_travel,
        raw.shear.travel_unit,
        "shear max dynamic travel",
    )
    max_static_comp_daN = _optional_static_to_daN(
        raw.max_static_comp,
        raw.max_static_comp_unit,
    )

    stiffness_sources = (comp_source, shear_source)
    validation_level = (
        "validated"
        if all(source == "published_shock_k" for source in stiffness_sources)
        else "screening_only"
    )
    warnings = _warnings_for_sources(stiffness_sources)

    spec = IsolatorSpec(
        name=f"{vendor} {part_no}",
        k_comp_Nm=k_comp_Nm,
        k_shear_Nm=k_shear_Nm,
        d_max_comp_mm=d_max_comp_mm,
        d_max_shear_mm=d_max_shear_mm,
        max_static_comp_daN=max_static_comp_daN,
    )
    return NormalizedCustomIsolator(
        spec=spec,
        vendor=vendor,
        part_no=part_no,
        source=raw.source,
        stiffness_source_comp=comp_source,
        stiffness_source_shear=shear_source,
        validation_level=validation_level,
        warnings=warnings,
    )


def _required_text(value: str, field_name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{field_name} is required")
    return text


def _positive(value: float, field_name: str) -> float:
    if value is None or value <= 0:
        raise ValidationError(f"{field_name} must be > 0")
    return float(value)


def _stiffness_to_Nm(stiffness: StiffnessInput) -> tuple[float, str]:
    if stiffness.method == "direct_k":
        return _direct_k_to_Nm(stiffness.value, stiffness.unit), "published_shock_k"
    if stiffness.method == "rated_load_frequency":
        mass_kg = _mass_to_kg(stiffness.value, stiffness.unit)
        frequency_hz = _positive(stiffness.frequency_hz, "frequency_hz")
        return mass_kg * (2.0 * math.pi * frequency_hz) ** 2, "derived_from_vibration_frequency"
    if stiffness.method == "force_deflection":
        force_N = _force_to_N(stiffness.value, stiffness.unit)
        deflection_m = _length_to_m(
            stiffness.deflection,
            stiffness.deflection_unit,
            "shock deflection",
        )
        return force_N / deflection_m, "derived_from_shock_load_deflection"
    raise ValidationError(f"unknown stiffness method: {stiffness.method}")


def _direct_k_to_Nm(value: float, unit: str) -> float:
    k = _positive(value, "stiffness")
    u = _norm_unit(unit)
    if u in ("n/m", "nm"):
        return k
    if u in ("n/mm", "nmm"):
        return k * _N_MM_TO_N_M
    if u in ("lb/in", "lbf/in", "lbfin"):
        return k * _LB_IN_TO_N_M
    raise ValidationError(f"unknown stiffness unit: {unit}")


def _mass_to_kg(value: float, unit: str) -> float:
    mass = _positive(value, "rated load")
    u = _norm_unit(unit)
    if u == "kg":
        return mass
    raise ValidationError(f"unknown rated load unit: {unit}")


def _force_to_N(value: float, unit: str) -> float:
    force = _positive(value, "force")
    u = _norm_unit(unit)
    if u == "n":
        return force
    if u == "dan":
        return force * 10.0
    if u == "kn":
        return force * 1000.0
    raise ValidationError(f"unknown force unit: {unit}")


def _length_to_mm(value: float, unit: str, field_name: str) -> float:
    length = _positive(value, field_name)
    u = _norm_unit(unit)
    if u == "mm":
        return length
    if u == "m":
        return length * 1000.0
    if u == "in":
        return length * _IN_TO_MM
    raise ValidationError(f"unknown length unit for {field_name}: {unit}")


def _length_to_m(value: float, unit: str, field_name: str) -> float:
    return _length_to_mm(value, unit, field_name) / 1000.0


def _optional_static_to_daN(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    load = _positive(value, "max_static_comp")
    u = _norm_unit(unit)
    if u == "dan":
        return load
    if u == "kg":
        return load * _KG_TO_DAN
    if u == "n":
        return load / 10.0
    raise ValidationError(f"unknown static load unit: {unit}")


def _warnings_for_sources(sources: tuple[str, str]) -> tuple[str, ...]:
    warnings = []
    if "derived_from_vibration_frequency" in sources:
        warnings.append(
            "Stiffness derived from vibration frequency; shock deflection is screening-only."
        )
    if "derived_from_shock_load_deflection" in sources:
        warnings.append(
            "Stiffness derived from shock load-deflection pair; use as average-K screening data."
        )
    return tuple(warnings)


def _norm_unit(unit: Optional[str]) -> str:
    if unit is None:
        raise ValidationError("unit is required")
    return unit.strip().lower().replace(" ", "")
