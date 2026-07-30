"""Build deterministic, serializable context for the Shock Selector assistant."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from typing import Any, Optional

from ui_selection_summary import summarize_selection


CONTEXT_ACTIONS = (
    (
        "Explain result",
        "Explain the current Shock Selector analysis result in plain engineering language.",
    ),
    (
        "Why this part?",
        "Why was the current isolator selected, and which constraint governed the choice?",
    ),
    (
        "Compare",
        "Compare the selected isolator with the nearest catalog alternatives in the current analysis.",
    ),
    (
        "Next checks",
        "What should the engineer check next before sending this current selection to the supplier?",
    ),
)


@dataclass(frozen=True)
class LoadCaseSnapshot:
    name: str
    status: str
    load_kg: float
    natural_frequency_hz: float
    transmitted_g: float
    transmitted_g_limit: float
    movement_mm: float
    movement_limit_mm: float
    impulse_model_valid: bool


@dataclass(frozen=True)
class AlternativeSnapshot:
    part_number: str
    series: str
    status: str
    worst_transmitted_g_use_pct: int
    worst_movement_use_pct: int
    worst_overall_use_pct: int


@dataclass(frozen=True)
class ShockAnalysisSnapshot:
    analysis_id: str
    mode: str
    verdict: str
    mass_kg: float
    bottom_mounts: int
    wall_mounts: int
    input_shock_g: float
    pulse_duration_ms: float
    pulse_shape: str
    transmitted_g_limit: float
    selected_part: Optional[str]
    selected_series: Optional[str]
    governing_case: Optional[str]
    governing_constraint: Optional[str]
    governing_use_pct: Optional[int]
    worst_transmitted_g: Optional[float]
    worst_movement_mm: Optional[float]
    static_load_daN: Optional[float]
    static_rating_daN: Optional[float]
    validation_level: Optional[str]
    load_cases: tuple[LoadCaseSnapshot, ...]
    alternatives: tuple[AlternativeSnapshot, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def label(self) -> str:
        part = self.selected_part or "no valid catalog part"
        return f"Linked to Analysis {self.analysis_id}: {part} | {self.verdict}"


def analysis_id_for_key(key: Any) -> str:
    """Return a stable short ID for the exact inputs behind one analysis."""
    payload = json.dumps(
        _jsonable(key),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8].upper()
    return f"S-{digest}"


def build_selection_snapshot(
    report,
    candidates,
    *,
    analysis_key: Any,
) -> ShockAnalysisSnapshot:
    """Build context from a catalog selection or single-part verification."""
    summary = summarize_selection(candidates)
    valid = [candidate for candidate in candidates if candidate.valid]
    selected = valid[0] if valid else None
    detail_candidate = selected or _closest_candidate(candidates)
    directions = _candidate_directions(detail_candidate)

    worst_gt = (
        max(directions, key=lambda direction: direction.GT_G / direction.GT_limit)
        if directions
        else None
    )
    worst_movement = (
        max(
            directions,
            key=lambda direction: direction.delta_mm / direction.delta_limit_mm,
        )
        if directions
        else None
    )
    warnings = tuple(str(warning) for warning in report.warnings)
    if selected is not None and selected.static_rating_daN is None:
        warnings += (
            "The selected part has no published static compression rating in "
            "the current catalog and requires vendor confirmation.",
        )

    return ShockAnalysisSnapshot(
        analysis_id=analysis_id_for_key(analysis_key),
        mode="catalog_selection",
        verdict="PASS" if selected is not None else "FAIL",
        mass_kg=round(float(report.mass_kg), 3),
        bottom_mounts=int(report.n_bottom),
        wall_mounts=int(report.n_wall),
        input_shock_g=round(float(report.shock_env.Ao_G), 3),
        pulse_duration_ms=round(float(report.shock_env.to_s) * 1000.0, 3),
        pulse_shape=str(report.shock_env.pulse_shape),
        transmitted_g_limit=round(float(report.shock_env.GT_limit_G), 3),
        selected_part=summary.recommended_part,
        selected_series=summary.series,
        governing_case=summary.limiting_case,
        governing_constraint=summary.limiting_constraint,
        governing_use_pct=summary.limiting_util_pct,
        worst_transmitted_g=_rounded(worst_gt.GT_G if worst_gt else None),
        worst_movement_mm=_rounded(
            worst_movement.delta_mm if worst_movement else None
        ),
        static_load_daN=_rounded(
            detail_candidate.static_load_daN if detail_candidate else None
        ),
        static_rating_daN=_rounded(
            detail_candidate.static_rating_daN if detail_candidate else None
        ),
        validation_level=None,
        load_cases=tuple(_load_case(direction) for direction in directions),
        alternatives=tuple(
            _alternative(candidate)
            for candidate in candidates
            if selected is None or candidate.entry.part_no != selected.entry.part_no
        )[:3],
        warnings=warnings,
    )


def build_custom_snapshot(
    result,
    *,
    analysis_key: Any,
) -> ShockAnalysisSnapshot:
    """Build context from a normalized custom/vendor isolator analysis."""
    report = result.report
    directions = tuple(report.directions)
    governing = _governing_direction(directions)
    worst_gt = max(
        directions,
        key=lambda direction: direction.GT_G / direction.GT_limit,
        default=None,
    )
    worst_movement = max(
        directions,
        key=lambda direction: direction.delta_mm / direction.delta_limit_mm,
        default=None,
    )
    governing_constraint = None
    governing_use_pct = None
    if governing is not None:
        governing_direction, governing_constraint, ratio = governing
        governing_case = governing_direction.label
        governing_use_pct = _pct(ratio)
    else:
        governing_case = None

    spec = result.normalized.spec
    return ShockAnalysisSnapshot(
        analysis_id=analysis_id_for_key(analysis_key),
        mode="custom_vendor",
        verdict=result.verdict,
        mass_kg=round(float(report.mass_kg), 3),
        bottom_mounts=int(report.n_bottom),
        wall_mounts=int(report.n_wall),
        input_shock_g=round(float(report.shock_env.Ao_G), 3),
        pulse_duration_ms=round(float(report.shock_env.to_s) * 1000.0, 3),
        pulse_shape=str(report.shock_env.pulse_shape),
        transmitted_g_limit=round(float(report.shock_env.GT_limit_G), 3),
        selected_part=spec.name,
        selected_series=None,
        governing_case=governing_case,
        governing_constraint=governing_constraint,
        governing_use_pct=governing_use_pct,
        worst_transmitted_g=_rounded(worst_gt.GT_G if worst_gt else None),
        worst_movement_mm=_rounded(
            worst_movement.delta_mm if worst_movement else None
        ),
        static_load_daN=_rounded(result.static_load_daN),
        static_rating_daN=_rounded(result.static_rating_daN),
        validation_level=result.validation_level,
        load_cases=tuple(_load_case(direction) for direction in directions),
        alternatives=(),
        warnings=tuple(str(warning) for warning in result.warnings),
    )


def build_runtime_context(
    snapshot: Optional[ShockAnalysisSnapshot],
    *,
    state: str,
) -> str:
    """Return an ephemeral system message for the current UI state."""
    if state == "stale":
        analysis_id = snapshot.analysis_id if snapshot else "unknown"
        return (
            "CURRENT SHOCK SELECTOR UI STATE\n"
            f"The stored Analysis {analysis_id} is stale because one or more "
            "inputs changed after it was calculated. Do not describe its part "
            "number, verdict, or numerical results as current. Ask the user to "
            "rerun the analysis. You may still answer general questions or run "
            "a new engineering tool when the user supplies the required inputs."
        )
    if state != "current" or snapshot is None:
        return (
            "CURRENT SHOCK SELECTOR UI STATE\n"
            "No current analysis result exists. Do not imply that the UI has a "
            "selected part or PASS/FAIL result. You may answer general questions "
            "and use the normal engineering tools when sufficient inputs exist."
        )

    payload = json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=True)
    return (
        "CURRENT SHOCK SELECTOR ANALYSIS\n"
        "The JSON below was generated by the validated Python calculation and "
        "is authoritative for explanations of the current UI result. For an "
        "explanation, summary, comparison, or next-check question, use these "
        "values without rerunning the calculation. Do not invent missing values. "
        "If the user requests changed inputs or a new calculation, use the normal "
        "engineering tools and present the change for confirmation rather than "
        "claiming that the UI was modified. Preserve all warnings and assumptions.\n"
        f"{payload}"
    )


def should_link_selector_result(
    snapshot: Optional[ShockAnalysisSnapshot],
    *,
    state: str,
    use_current_result: bool,
) -> bool:
    """Return whether the assistant may receive the current selector snapshot."""
    return bool(
        use_current_result
        and state == "current"
        and snapshot is not None
    )


def _load_case(direction) -> LoadCaseSnapshot:
    return LoadCaseSnapshot(
        name=str(direction.label),
        status="PASS" if direction.passed else "FAIL",
        load_kg=round(float(direction.m_kg), 3),
        natural_frequency_hz=round(float(direction.fn_Hz), 3),
        transmitted_g=round(float(direction.GT_G), 3),
        transmitted_g_limit=round(float(direction.GT_limit), 3),
        movement_mm=round(float(direction.delta_mm), 3),
        movement_limit_mm=round(float(direction.delta_limit_mm), 3),
        impulse_model_valid=bool(direction.impulse_valid),
    )


def _alternative(candidate) -> AlternativeSnapshot:
    return AlternativeSnapshot(
        part_number=str(candidate.entry.part_no),
        series=str(candidate.entry.series),
        status="PASS" if candidate.valid else "FAIL",
        worst_transmitted_g_use_pct=_pct(candidate.worst_GT_ratio),
        worst_movement_use_pct=_pct(candidate.worst_delta_ratio),
        worst_overall_use_pct=_pct(candidate.worst_overall_ratio),
    )


def _candidate_directions(candidate) -> tuple:
    if candidate is None:
        return ()
    return (
        candidate.comp_bottom,
        candidate.comp_wall,
        candidate.roll_wall,
        candidate.roll_bottom,
    )


def _closest_candidate(candidates):
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: candidate.worst_overall_ratio)


def _governing_direction(directions: tuple):
    limits = []
    for direction in directions:
        limits.append(
            (direction, "GT", direction.GT_G / direction.GT_limit)
        )
        limits.append(
            (
                direction,
                "deflection",
                direction.delta_mm / direction.delta_limit_mm,
            )
        )
    return max(limits, key=lambda item: item[2], default=None)


def _pct(ratio: float) -> int:
    return int(round(float(ratio) * 100.0))


def _rounded(value: Optional[float], places: int = 3) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), places)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)
