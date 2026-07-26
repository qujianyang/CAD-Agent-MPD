"""Deterministic evidence checks for AI explanations of shock results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import re
from typing import Any, Mapping, Optional


STATUS_VERIFIED = "Verified"
STATUS_VERIFIED_WITH_ASSUMPTIONS = "Verified with assumptions"
STATUS_REVIEW_REQUIRED = "Review required"
STATUS_INSUFFICIENT_INFORMATION = "Insufficient information"
STATUS_UNSUPPORTED_RESPONSE = "Unsupported response"


@dataclass(frozen=True)
class AssuranceCheck:
    name: str
    outcome: str
    detail: str


@dataclass(frozen=True)
class ResponseAssurance:
    status: str
    summary: str
    checks: tuple[AssuranceCheck, ...]
    supported_numeric_claims: int = 0
    total_numeric_claims: int = 0
    unsupported_claims: tuple[str, ...] = ()


_ANALYSIS_ID_RE = re.compile(r"\bS-[A-F0-9]{8}\b", re.IGNORECASE)
_VERDICT_RE = re.compile(
    r"\b(PASS(?:ES|ED)?|FAIL(?:S|ED)?|ASK)\b",
    re.IGNORECASE,
)
_CATALOG_PART_RE = re.compile(r"\bCB\d{4}-\d+\b", re.IGNORECASE)
_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![\w.-])"
    r"(?P<value>-?\d+(?:,\d{3})*(?:\.\d+)?)"
    r"\s*"
    r"(?P<unit>daN|N/mm|kg|mm|ms|Hz|G|%)"
    r"(?![A-Za-z/])",
    re.IGNORECASE,
)

_UNIT_TOLERANCE = {
    "dan": 0.5,
    "n/mm": 0.05,
    "kg": 0.5,
    "mm": 0.15,
    "ms": 0.1,
    "hz": 0.15,
    "g": 0.15,
    "%": 1.0,
}

_WARNING_TOPICS = {
    "vendor confirmation": ("vendor", "supplier", "published", "rating"),
    "clearance": ("clearance", "gap", "contact"),
    "impulse-model validity": ("impulse", "pulse", "model validity", "validity"),
    "vibration": ("vibration", "resonance", "psd"),
    "static capacity": ("static", "capacity"),
    "derived data": ("derived", "screening", "assumption"),
    "travel": ("travel", "movement", "deflection"),
    "damping": ("damping", "damped"),
}


def check_response(
    answer: str,
    snapshot: Any,
    *,
    linked_analysis_id: Optional[str] = None,
    current_analysis_id: Optional[str] = None,
    current_state: str = "current",
) -> ResponseAssurance:
    """Check whether a live explanation is supported by one Python snapshot.

    This is an evidence-consistency check, not a prediction of response accuracy
    and not a substitute for physical qualification.
    """
    text = str(answer or "").strip()
    payload = _snapshot_dict(snapshot)
    if not text or not payload:
        return ResponseAssurance(
            status=STATUS_INSUFFICIENT_INFORMATION,
            summary="A response and linked engineering result are required.",
            checks=(),
        )

    expected_id = str(payload.get("analysis_id") or "")
    expected_verdict = str(payload.get("verdict") or "").upper()
    checks: list[AssuranceCheck] = []
    unsupported_reasons: list[str] = []
    review_reasons: list[str] = []

    metadata_matches = not linked_analysis_id or linked_analysis_id == expected_id
    checks.append(
        AssuranceCheck(
            "Analysis link",
            "pass" if metadata_matches else "fail",
            (
                f"Response is linked to {expected_id}."
                if metadata_matches
                else f"Response metadata does not match snapshot {expected_id}."
            ),
        )
    )
    if not metadata_matches:
        unsupported_reasons.append("analysis link mismatch")

    stated_ids = {match.upper() for match in _ANALYSIS_ID_RE.findall(text)}
    id_claim_matches = not stated_ids or stated_ids == {expected_id.upper()}
    checks.append(
        AssuranceCheck(
            "Analysis ID stated in answer",
            "pass" if id_claim_matches else "fail",
            (
                f"Stated ID agrees with {expected_id}."
                if stated_ids and id_claim_matches
                else "No analysis ID was stated."
                if not stated_ids
                else "The answer names a different analysis ID."
            ),
        )
    )
    if not id_claim_matches:
        unsupported_reasons.append("incorrect analysis ID")

    is_current = (
        current_state == "current"
        and (not current_analysis_id or current_analysis_id == expected_id)
    )
    checks.append(
        AssuranceCheck(
            "Current UI state",
            "pass" if is_current else "attention",
            (
                "The linked result is current."
                if is_current
                else "The response is historical or the selector inputs have changed."
            ),
        )
    )
    if not is_current:
        review_reasons.append("linked result is not current")

    stated_verdicts = {_normalize_verdict(value) for value in _VERDICT_RE.findall(text)}
    verdict_matches = not stated_verdicts or stated_verdicts == {expected_verdict}
    checks.append(
        AssuranceCheck(
            "Verdict",
            "pass" if verdict_matches else "fail",
            (
                f"Stated verdict agrees with Python: {expected_verdict}."
                if stated_verdicts and verdict_matches
                else "The response does not state a verdict."
                if not stated_verdicts
                else f"Python returned {expected_verdict}, but the response disagrees."
            ),
        )
    )
    if not verdict_matches:
        unsupported_reasons.append("verdict mismatch")

    allowed_parts = _allowed_parts(payload)
    stated_parts = {part.upper() for part in _CATALOG_PART_RE.findall(text)}
    unknown_parts = sorted(stated_parts - allowed_parts)
    checks.append(
        AssuranceCheck(
            "Catalog parts",
            "pass" if not unknown_parts else "fail",
            (
                "Every stated catalog part appears in the linked result."
                if stated_parts and not unknown_parts
                else "The response does not state a catalog part."
                if not stated_parts
                else "Unsupported part(s): " + ", ".join(unknown_parts)
            ),
        )
    )
    if unknown_parts:
        unsupported_reasons.append("unsupported catalog part")

    numeric_claims = _extract_numeric_claims(text)
    evidence = _numeric_evidence(payload)
    unsupported_numbers = tuple(
        claim
        for claim, value, unit in numeric_claims
        if not _matches_evidence(value, unit, evidence)
    )
    supported_count = len(numeric_claims) - len(unsupported_numbers)
    checks.append(
        AssuranceCheck(
            "Engineering numbers",
            "pass" if not unsupported_numbers else "fail",
            (
                f"{supported_count}/{len(numeric_claims)} unit-bearing values "
                "match the linked Python result."
                if numeric_claims
                else "No unit-bearing engineering values were stated."
            ),
        )
    )
    if unsupported_numbers:
        unsupported_reasons.append("unsupported engineering number")

    warnings = tuple(str(item) for item in payload.get("warnings") or ())
    required_topics = _warning_topics(warnings)
    covered_topics = {
        topic
        for topic, terms in required_topics.items()
        if any(term in text.lower() for term in terms)
    }
    missing_topics = sorted(set(required_topics) - covered_topics)
    if warnings:
        warnings_ok = not missing_topics
        checks.append(
            AssuranceCheck(
                "Warnings and assumptions",
                "pass" if warnings_ok else "attention",
                (
                    f"All {len(required_topics)} warning topic(s) are acknowledged."
                    if warnings_ok
                    else "Review omitted topic(s): " + ", ".join(missing_topics)
                    if missing_topics
                    else f"{len(warnings)} warning(s) require engineering review."
                ),
            )
        )
        if not warnings_ok:
            review_reasons.append("warning or assumption omitted")
    else:
        checks.append(
            AssuranceCheck(
                "Warnings and assumptions",
                "pass",
                "The linked Python result contains no warnings.",
            )
        )

    if unsupported_reasons:
        status = STATUS_UNSUPPORTED_RESPONSE
        summary = (
            "One or more claims conflict with, or are absent from, the linked "
            "engineering evidence."
        )
    elif review_reasons:
        status = STATUS_REVIEW_REQUIRED
        summary = "The response is partly supported but requires engineer review."
    elif warnings or _has_assumptions(payload):
        status = STATUS_VERIFIED_WITH_ASSUMPTIONS
        summary = "The response agrees with the linked result and its stated assumptions."
    else:
        status = STATUS_VERIFIED
        summary = "The response agrees with the linked deterministic result."

    return ResponseAssurance(
        status=status,
        summary=summary,
        checks=tuple(checks),
        supported_numeric_claims=supported_count,
        total_numeric_claims=len(numeric_claims),
        unsupported_claims=unsupported_numbers,
    )


def _snapshot_dict(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    if hasattr(snapshot, "to_dict"):
        return dict(snapshot.to_dict())
    if is_dataclass(snapshot):
        return asdict(snapshot)
    return {}


def _allowed_parts(payload: Mapping[str, Any]) -> set[str]:
    parts = set()
    selected = payload.get("selected_part")
    if selected:
        parts.update(part.upper() for part in _CATALOG_PART_RE.findall(str(selected)))
    for alternative in payload.get("alternatives") or ():
        part = alternative.get("part_number") if isinstance(alternative, Mapping) else None
        if part:
            parts.add(str(part).upper())
    return parts


def _numeric_evidence(payload: Mapping[str, Any]) -> dict[str, list[float]]:
    evidence: dict[str, list[float]] = {
        "kg": [],
        "g": [],
        "mm": [],
        "ms": [],
        "hz": [],
        "dan": [],
        "n/mm": [],
        "%": [],
    }
    _append_number(evidence["kg"], payload.get("mass_kg"))
    _append_number(evidence["g"], payload.get("input_shock_g"))
    _append_number(evidence["g"], payload.get("transmitted_g_limit"))
    _append_number(evidence["g"], payload.get("worst_transmitted_g"))
    _append_number(evidence["mm"], payload.get("worst_movement_mm"))
    _append_number(evidence["ms"], payload.get("pulse_duration_ms"))
    _append_number(evidence["dan"], payload.get("static_load_daN"))
    _append_number(evidence["dan"], payload.get("static_rating_daN"))
    _append_number(evidence["%"], payload.get("governing_use_pct"))

    for load_case in payload.get("load_cases") or ():
        if not isinstance(load_case, Mapping):
            continue
        _append_number(evidence["kg"], load_case.get("load_kg"))
        _append_number(evidence["hz"], load_case.get("natural_frequency_hz"))
        _append_number(evidence["g"], load_case.get("transmitted_g"))
        _append_number(evidence["g"], load_case.get("transmitted_g_limit"))
        _append_number(evidence["mm"], load_case.get("movement_mm"))
        _append_number(evidence["mm"], load_case.get("movement_limit_mm"))
        _append_ratio(
            evidence["%"],
            load_case.get("transmitted_g"),
            load_case.get("transmitted_g_limit"),
        )
        _append_ratio(
            evidence["%"],
            load_case.get("movement_mm"),
            load_case.get("movement_limit_mm"),
        )

    for alternative in payload.get("alternatives") or ():
        if not isinstance(alternative, Mapping):
            continue
        _append_number(evidence["%"], alternative.get("worst_transmitted_g_use_pct"))
        _append_number(evidence["%"], alternative.get("worst_movement_use_pct"))
        _append_number(evidence["%"], alternative.get("worst_overall_use_pct"))
    return evidence


def _extract_numeric_claims(text: str) -> list[tuple[str, float, str]]:
    claims = []
    for match in _NUMBER_WITH_UNIT_RE.finditer(text):
        raw_value = match.group("value")
        unit = match.group("unit").lower()
        claims.append(
            (
                match.group(0).strip(),
                float(raw_value.replace(",", "")),
                unit,
            )
        )
    return claims


def _matches_evidence(
    value: float,
    unit: str,
    evidence: Mapping[str, list[float]],
) -> bool:
    absolute_tolerance = _UNIT_TOLERANCE[unit]
    return any(
        abs(value - expected)
        <= max(absolute_tolerance, 0.015 * max(abs(expected), 1.0))
        for expected in evidence.get(unit, ())
    )


def _append_number(target: list[float], value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    try:
        target.append(float(value))
    except (TypeError, ValueError):
        return


def _append_ratio(target: list[float], numerator: Any, denominator: Any) -> None:
    try:
        denominator_value = float(denominator)
        if denominator_value:
            target.append(round(float(numerator) / denominator_value * 100.0))
    except (TypeError, ValueError):
        return


def _warning_topics(warnings: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    warning_text = " ".join(warnings).lower()
    return {
        topic: terms
        for topic, terms in _WARNING_TOPICS.items()
        if any(term in warning_text for term in terms)
    }


def _has_assumptions(payload: Mapping[str, Any]) -> bool:
    level = str(payload.get("validation_level") or "").strip().lower()
    return bool(level and level not in {"validated", "direct"})


def _normalize_verdict(value: str) -> str:
    upper = value.upper()
    if upper.startswith("PASS"):
        return "PASS"
    if upper.startswith("FAIL"):
        return "FAIL"
    return "ASK"
