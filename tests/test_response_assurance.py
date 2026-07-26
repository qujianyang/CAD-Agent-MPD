from response_assurance import (
    STATUS_REVIEW_REQUIRED,
    STATUS_UNSUPPORTED_RESPONSE,
    STATUS_VERIFIED,
    STATUS_VERIFIED_WITH_ASSUMPTIONS,
    check_response,
)


def _snapshot(**overrides):
    payload = {
        "analysis_id": "S-1234ABCD",
        "mode": "catalog_selection",
        "verdict": "PASS",
        "mass_kg": 850.0,
        "bottom_mounts": 6,
        "wall_mounts": 4,
        "input_shock_g": 20.0,
        "pulse_duration_ms": 11.0,
        "pulse_shape": "sawtooth",
        "transmitted_g_limit": 10.0,
        "selected_part": "CB1700-20",
        "selected_series": "CB1700",
        "governing_case": "Wall mounts in Y-axis compression",
        "governing_constraint": "transmitted shock (GT)",
        "governing_use_pct": 86,
        "worst_transmitted_g": 8.58,
        "worst_movement_mm": 20.0,
        "static_load_daN": 1.39,
        "static_rating_daN": 10.4,
        "validation_level": None,
        "load_cases": [
            {
                "name": "Wall mounts in Y-axis compression",
                "status": "PASS",
                "load_kg": 21.25,
                "natural_frequency_hz": 12.4,
                "transmitted_g": 8.58,
                "transmitted_g_limit": 10.0,
                "movement_mm": 20.0,
                "movement_limit_mm": 71.1,
                "impulse_model_valid": True,
            }
        ],
        "alternatives": [
            {
                "part_number": "CB1700-30",
                "series": "CB1700",
                "status": "PASS",
                "worst_transmitted_g_use_pct": 92,
                "worst_movement_use_pct": 24,
                "worst_overall_use_pct": 92,
            }
        ],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


def test_verified_response_matches_linked_result_with_rounded_numbers():
    result = check_response(
        (
            "Analysis S-1234ABCD is PASS. CB1700-20 was selected for the "
            "850 kg system under 20 G for 11 ms. The worst transmitted "
            "shock is 8.6 G against the 10 G limit, or 86%."
        ),
        _snapshot(),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
        current_state="current",
    )

    assert result.status == STATUS_VERIFIED
    assert result.supported_numeric_claims == result.total_numeric_claims
    assert not result.unsupported_claims


def test_wrong_verdict_and_unsupported_number_are_rejected():
    result = check_response(
        "CB1700-20 FAILS because the transmitted shock is 12.4 G.",
        _snapshot(),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
        current_state="current",
    )

    assert result.status == STATUS_UNSUPPORTED_RESPONSE
    assert result.unsupported_claims == ("12.4 G",)
    assert any(check.name == "Verdict" and check.outcome == "fail"
               for check in result.checks)


def test_stale_ui_requires_review_even_when_historical_answer_matches():
    result = check_response(
        "The historical result was PASS at 8.58 G.",
        _snapshot(),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-99999999",
        current_state="stale",
    )

    assert result.status == STATUS_REVIEW_REQUIRED
    assert any(check.name == "Current UI state" and check.outcome == "attention"
               for check in result.checks)


def test_warnings_produce_verified_with_assumptions_when_acknowledged():
    result = check_response(
        (
            "CB1700-20 passes, but the static capacity and published rating "
            "still require vendor confirmation."
        ),
        _snapshot(
            warnings=[
                "The selected part has no published static compression rating "
                "and requires vendor confirmation."
            ]
        ),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
        current_state="current",
    )

    assert result.status == STATUS_VERIFIED_WITH_ASSUMPTIONS


def test_omitted_warning_requires_review():
    result = check_response(
        "CB1700-20 passes the calculated shock cases.",
        _snapshot(
            warnings=[
                "The selected part has no published static compression rating "
                "and requires vendor confirmation."
            ]
        ),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
        current_state="current",
    )

    assert result.status == STATUS_REVIEW_REQUIRED


def test_known_alternative_is_supported_but_unknown_catalog_part_is_not():
    supported = check_response(
        "Compare CB1700-20 with CB1700-30.",
        _snapshot(),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
    )
    unsupported = check_response(
        "Compare CB1700-20 with CB1400-99.",
        _snapshot(),
        linked_analysis_id="S-1234ABCD",
        current_analysis_id="S-1234ABCD",
    )

    assert supported.status == STATUS_VERIFIED
    assert unsupported.status == STATUS_UNSUPPORTED_RESPONSE
