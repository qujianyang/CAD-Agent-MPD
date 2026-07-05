"""Pure UI summary helpers for shock-isolator selection results.

This module intentionally has no Streamlit dependency so the user-facing
decision logic can be tested without launching the app.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SelectionSummary:
    verdict: str
    recommended_part: Optional[str]
    series: Optional[str]
    headline: str
    support_line: str
    next_action: str
    worst_gt_pct: Optional[int] = None
    worst_delta_pct: Optional[int] = None
    limiting_case: Optional[str] = None
    limiting_constraint: Optional[str] = None
    limiting_util_pct: Optional[int] = None
    static_status: str = "unknown"
    static_text: str = ""


def _pct(ratio: float) -> int:
    return int(round(ratio * 100.0))


def _rounded(value: Optional[float], places: int = 6) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), places)


_SELECTION_KEY_LABELS = (
    "mode",
    "mass",
    "bottom mounts",
    "wall mounts",
    "shock G",
    "pulse duration",
    "GT limit",
    "pulse profile",
    "clearance X",
    "clearance Y",
    "clearance Z",
    "catalog filter",
    "selection objective",
    "selected part",
)


def build_shock_selection_key(
    *,
    mode: str,
    mass_kg: float,
    n_bottom: int,
    n_wall: int,
    Ao_G: float,
    to_s: float,
    GT_limit_G: float,
    pulse_shape: str,
    clr_x_mm: float,
    clr_y_mm: float,
    clr_z_mm: float,
    catalog_label: Optional[str],
    objective: Optional[str],
    part_no: Optional[str],
) -> tuple:
    """Return a stable signature for the inputs behind a shock selection run."""
    return (
        mode,
        _rounded(mass_kg),
        int(n_bottom),
        int(n_wall),
        _rounded(Ao_G),
        _rounded(to_s),
        _rounded(GT_limit_G),
        pulse_shape,
        _rounded(clr_x_mm),
        _rounded(clr_y_mm),
        _rounded(clr_z_mm),
        catalog_label,
        objective,
        part_no,
    )


def describe_selection_key_changes(old_key, new_key) -> str:
    """Return readable field names that changed between two selection signatures."""
    if not old_key or not new_key or len(old_key) != len(new_key):
        return "Inputs changed since this result was computed."
    changed = [
        label
        for label, old_value, new_value in zip(_SELECTION_KEY_LABELS, old_key, new_key)
        if old_value != new_value
    ]
    if not changed:
        return ""
    return "Changed inputs: " + ", ".join(changed) + "."


def build_candidate_comparison_rows(candidates) -> list[dict]:
    """Return scan-friendly rows for the catalog comparison table."""
    rows = []
    for candidate in candidates:
        direction, constraint, ratio = _limiting_constraint(candidate)
        static_text = "vendor check"
        if candidate.static_util is not None:
            static_text = _format_pct(candidate.static_util)
        rows.append(
            {
                "Part": candidate.entry.part_no,
                "Series": candidate.entry.series,
                "Status": "PASS" if candidate.valid else "FAIL",
                "Worst use": _format_pct(candidate.worst_overall_ratio),
                "Limiting constraint": f"{direction.label} {constraint}",
                "Worst GT": _format_pct(candidate.worst_GT_ratio),
                "Worst deflection": _format_pct(candidate.worst_delta_ratio),
                "Static load": static_text,
            }
        )
    return rows


def build_load_case_rows(candidate) -> list[dict]:
    """Return scan-friendly rows for the recommended part's four load cases."""
    cases = [
        (candidate.comp_bottom, candidate.entry.d_max_comp_mm),
        (candidate.comp_wall, candidate.entry.d_max_comp_mm),
        (candidate.roll_wall, candidate.entry.d_max_shear_mm),
        (candidate.roll_bottom, candidate.entry.d_max_shear_mm),
    ]
    rows = []
    for direction, dmax_raw in cases:
        gt_ratio = direction.GT_G / direction.GT_limit
        delta_ratio = direction.delta_mm / direction.delta_limit_mm
        limit_ratio = max(gt_ratio, delta_ratio)
        constraint = "GT" if gt_ratio >= delta_ratio else "deflection"
        limit_src = (
            "clearance"
            if direction.delta_limit_mm < dmax_raw - 1e-6
            else "travel"
        )
        binding = constraint if constraint == "GT" else f"deflection ({limit_src})"
        rows.append(
            {
                "Case": direction.label,
                "Status": "PASS" if direction.passed else "FAIL",
                "Limit use": _format_pct(limit_ratio),
                "Margin": _margin_text(limit_ratio),
                "Binding": binding,
                "GT [G]": round(direction.GT_G, 3),
                "dD [mm]": round(direction.delta_mm, 2),
                "Load [kg]": round(direction.m_kg, 2),
            }
        )
    return rows


def _format_pct(ratio: float) -> str:
    return f"{_pct(ratio)}%"


def _margin_text(ratio: float) -> str:
    pct = _pct(abs(1.0 - ratio))
    if ratio <= 1.0:
        return f"{pct}% remaining"
    return f"{pct}% over"


def format_assessment_context(
    *,
    mass_kg: float,
    n_bottom: int,
    n_wall: int,
    Ao_G: float,
    to_s: float,
    GT_limit_G: float,
    pulse_shape: str,
) -> str:
    """Return compact text describing the setup behind a shock assessment."""
    to_ms = to_s * 1000.0
    return (
        f"{mass_kg:.1f} kg | {int(n_bottom)} bottom + {int(n_wall)} wall mounts | "
        f"{Ao_G:.1f} G {pulse_shape} shock, {to_ms:.1f} ms pulse | "
        f"GT limit {GT_limit_G:.1f} G"
    )


def _directions(candidate):
    return [
        candidate.comp_bottom,
        candidate.comp_wall,
        candidate.roll_wall,
        candidate.roll_bottom,
    ]


def _limiting_constraint(candidate):
    limits = []
    for direction in _directions(candidate):
        limits.append((direction, "GT", direction.GT_G / direction.GT_limit))
        limits.append((
            direction,
            "deflection",
            direction.delta_mm / direction.delta_limit_mm,
        ))
    return max(limits, key=lambda item: item[2])


def _blocking_constraints(candidate):
    limits = list(_dynamic_constraints(candidate))
    if candidate.static_rating_daN is not None:
        limits.append((None, "static load", candidate.static_util))
    return limits


def _dynamic_constraints(candidate):
    for direction in _directions(candidate):
        yield (direction, "GT", direction.GT_G / direction.GT_limit)
        yield (
            direction,
            "deflection",
            direction.delta_mm / direction.delta_limit_mm,
        )


def _closest_failed_candidate(candidates):
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: max(ratio for _, _, ratio in _blocking_constraints(candidate)),
    )


def _failed_candidate_detail(candidate) -> tuple[str, str]:
    direction, constraint, ratio = max(
        _blocking_constraints(candidate),
        key=lambda item: item[2],
    )
    pct = _pct(ratio)
    if direction is None:
        detail = f"static load uses {pct}% of its catalog rating."
        action = "Try more bottom mounts, a part with a higher static rating, or a lighter supported mass."
    elif constraint == "GT":
        detail = f"{direction.label}; GT uses {pct}% of its limit."
        action = "Try more mounts, a stiffer/larger series, or confirm a higher allowable GT limit."
    else:
        detail = f"{direction.label}; deflection uses {pct}% of its limit."
        action = "Try more installation clearance, more mounts, or a stiffer/larger part."
    return detail, action


def _static_summary(candidate) -> tuple[str, str]:
    load = candidate.static_load_daN
    rating = candidate.static_rating_daN
    if rating is None:
        return (
            "unrated",
            f"Static load is {load:.0f} daN per bottom mount; no catalog rating is published. Verify with vendor data.",
        )
    util = candidate.static_util
    if candidate.static_ok:
        return (
            "rated",
            f"Static load is {load:.0f}/{rating:.0f} daN per bottom mount ({_pct(util)}% of rating).",
        )
    return (
        "overloaded",
        f"Static load is {load:.0f}/{rating:.0f} daN per bottom mount ({_pct(util)}% of rating), above the catalog limit.",
    )


def summarize_selection(candidates) -> SelectionSummary:
    """Return a compact, user-facing summary for a sorted candidate list."""
    valid = [candidate for candidate in candidates if candidate.valid]
    if not valid:
        closest = _closest_failed_candidate(candidates)
        if closest is None:
            support_line = "No catalog entries were available for the selected filter."
            next_action = "Choose a catalog series or switch back to the default catalog filter."
        else:
            detail, next_action = _failed_candidate_detail(closest)
            support_line = (
                f"Closest candidate is {closest.entry.part_no}, but it still fails: {detail}"
            )
        return SelectionSummary(
            verdict="NO_VALID_PART",
            recommended_part=None,
            series=None,
            headline="No catalog part passes the selected constraints.",
            support_line=support_line,
            next_action=next_action,
        )

    rec = valid[0]
    direction, constraint, limit_ratio = _limiting_constraint(rec)
    static_status, static_text = _static_summary(rec)
    worst_gt_pct = _pct(rec.worst_GT_ratio)
    worst_delta_pct = _pct(rec.worst_delta_ratio)
    limiting_pct = _pct(limit_ratio)
    part_no = rec.entry.part_no

    next_action = (
        f"Use {part_no} as the current recommendation, then review the four load cases before committing."
    )
    if static_status == "unrated":
        next_action = (
            f"Use {part_no} only after vendor static-load verification, then review the four load cases."
        )

    return SelectionSummary(
        verdict="PASS",
        recommended_part=part_no,
        series=rec.entry.series,
        headline=f"{part_no} passes all four shock load cases.",
        support_line=(
            f"Limiting case: {direction.label}; {constraint} uses {limiting_pct}% of its limit. "
            f"Worst GT is {worst_gt_pct}% and worst deflection is {worst_delta_pct}%."
        ),
        next_action=next_action,
        worst_gt_pct=worst_gt_pct,
        worst_delta_pct=worst_delta_pct,
        limiting_case=direction.label,
        limiting_constraint=constraint,
        limiting_util_pct=limiting_pct,
        static_status=static_status,
        static_text=static_text,
    )
