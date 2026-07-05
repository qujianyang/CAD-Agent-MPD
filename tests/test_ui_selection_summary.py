from catalog import CatalogCandidate, CatalogEntry
from physics_engine import DirectionResult
from ui_selection_summary import (
    build_candidate_comparison_rows,
    build_load_case_rows,
    build_review_next_rows,
    build_shock_selection_key,
    describe_selection_key_changes,
    format_assessment_context,
    summarize_selection,
)


def _direction(label, *, gt, gt_limit=10.0, delta, delta_limit=40.0):
    return DirectionResult(
        label=label,
        k_Nm=100000.0,
        m_kg=100.0,
        V_ms=1.0,
        fn_Hz=5.0,
        GT_G=gt,
        delta_mm=delta,
        GT_limit=gt_limit,
        delta_limit_mm=delta_limit,
    )


def _candidate(
    *,
    part_no="CB1400-15",
    k_comp=2650,
    static_load=100.0,
    static_rating=200.0,
    directions=None,
):
    entry = CatalogEntry(
        part_no,
        H_in=3.25,
        W_in=4.0,
        k_comp_lbin=k_comp,
        k_shear_lbin=1080,
        d_max_comp_in=1.4,
        d_max_shear_in=1.6,
        max_static_comp_daN=static_rating,
    )
    dirs = directions or [
        _direction("Comp - Bottom (Z-axis)", gt=5.0, delta=12.0),
        _direction("Comp - Wall (Y-axis)", gt=4.0, delta=10.0),
        _direction("Roll - Wall (X,Z-axis)", gt=3.0, delta=8.0),
        _direction("Roll - Bottom (X,Y-axis)", gt=6.0, delta=28.0),
    ]
    return CatalogCandidate(
        entry=entry,
        comp_bottom=dirs[0],
        comp_wall=dirs[1],
        roll_wall=dirs[2],
        roll_bottom=dirs[3],
        static_load_daN=static_load,
        static_rating_daN=static_rating,
    )


def test_summary_highlights_recommendation_and_binding_constraint():
    summary = summarize_selection([_candidate()])

    assert summary.verdict == "PASS"
    assert summary.recommended_part == "CB1400-15"
    assert summary.worst_gt_pct == 60
    assert summary.worst_delta_pct == 70
    assert summary.limiting_case == "Roll - Bottom (X,Y-axis)"
    assert summary.limiting_constraint == "deflection"
    assert summary.limiting_util_pct == 70
    assert summary.static_status == "rated"
    assert "Use CB1400-15" in summary.next_action


def test_review_next_rows_turn_summary_into_decision_checklist():
    summary = summarize_selection([_candidate()])

    rows = build_review_next_rows(summary)

    assert [row["Review"] for row in rows] == [
        "Chosen part",
        "Limiting case",
        "Engineering check",
    ]
    assert rows[0]["Focus"] == "CB1400-15"
    assert "Roll - Bottom" in rows[1]["Focus"]
    assert "70% used" in rows[1]["Focus"]
    assert rows[2]["Focus"] == "Review all four load cases"


def test_summary_flags_unrated_static_load_as_vendor_check():
    summary = summarize_selection([_candidate(static_rating=None)])

    assert summary.verdict == "PASS"
    assert summary.static_status == "unrated"
    assert "vendor" in summary.static_text.lower()
    assert "vendor" in summary.next_action.lower()


def test_summary_handles_no_valid_candidates():
    failed = _candidate(
        directions=[
            _direction("Comp - Bottom (Z-axis)", gt=12.0, delta=12.0),
            _direction("Comp - Wall (Y-axis)", gt=4.0, delta=10.0),
            _direction("Roll - Wall (X,Z-axis)", gt=3.0, delta=8.0),
            _direction("Roll - Bottom (X,Y-axis)", gt=6.0, delta=28.0),
        ]
    )

    summary = summarize_selection([failed])

    assert summary.verdict == "NO_VALID_PART"
    assert summary.recommended_part is None
    assert "more mounts" in summary.next_action.lower()


def test_no_valid_summary_names_closest_part_and_blocking_constraint():
    worse = _candidate(
        part_no="CB1400-15",
        k_comp=2650,
        directions=[
            _direction("Comp - Bottom (Z-axis)", gt=15.0, delta=12.0),
            _direction("Comp - Wall (Y-axis)", gt=4.0, delta=10.0),
            _direction("Roll - Wall (X,Z-axis)", gt=3.0, delta=8.0),
            _direction("Roll - Bottom (X,Y-axis)", gt=6.0, delta=28.0),
        ],
    )
    closer = _candidate(
        part_no="CB1500-15",
        k_comp=3655,
        directions=[
            _direction("Comp - Bottom (Z-axis)", gt=11.0, delta=12.0),
            _direction("Comp - Wall (Y-axis)", gt=4.0, delta=10.0),
            _direction("Roll - Wall (X,Z-axis)", gt=3.0, delta=8.0),
            _direction("Roll - Bottom (X,Y-axis)", gt=6.0, delta=28.0),
        ],
    )

    summary = summarize_selection([worse, closer])

    assert "CB1500-15" in summary.support_line
    assert "Comp - Bottom" in summary.support_line
    assert "GT" in summary.support_line
    assert "110%" in summary.support_line


def test_selection_key_changes_when_inputs_change():
    base = build_shock_selection_key(
        mode="auto",
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0,
        to_s=0.011,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
        clr_x_mm=0.0,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label="All series",
        objective="balanced",
        part_no=None,
    )
    changed = build_shock_selection_key(
        mode="auto",
        mass_kg=900.0,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0,
        to_s=0.011,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
        clr_x_mm=0.0,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label="All series",
        objective="balanced",
        part_no=None,
    )

    assert base != changed


def test_selection_key_rounds_float_noise():
    base = build_shock_selection_key(
        mode="manual",
        mass_kg=850.0000001,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0000001,
        to_s=0.0110000001,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
        clr_x_mm=1.0000001,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label=None,
        objective=None,
        part_no="CB1400-15",
    )
    same = build_shock_selection_key(
        mode="manual",
        mass_kg=850.0000002,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0000002,
        to_s=0.0110000002,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
        clr_x_mm=1.0000002,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label=None,
        objective=None,
        part_no="CB1400-15",
    )

    assert base == same


def test_assessment_context_formats_user_inputs():
    text = format_assessment_context(
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0,
        to_s=0.011,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
    )

    assert "850.0 kg" in text
    assert "6 bottom + 4 wall" in text
    assert "20.0 G sawtooth" in text
    assert "11.0 ms" in text
    assert "GT limit 10.0 G" in text


def test_selection_key_change_description_names_changed_inputs():
    old = build_shock_selection_key(
        mode="auto",
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0,
        to_s=0.011,
        GT_limit_G=10.0,
        pulse_shape="sawtooth",
        clr_x_mm=0.0,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label="All series",
        objective="balanced",
        part_no=None,
    )
    new = build_shock_selection_key(
        mode="auto",
        mass_kg=900.0,
        n_bottom=6,
        n_wall=4,
        Ao_G=20.0,
        to_s=0.011,
        GT_limit_G=12.0,
        pulse_shape="sawtooth",
        clr_x_mm=0.0,
        clr_y_mm=0.0,
        clr_z_mm=0.0,
        catalog_label="All series",
        objective="balanced",
        part_no=None,
    )

    description = describe_selection_key_changes(old, new)

    assert description == "Changed inputs: mass, GT limit."


def test_candidate_comparison_rows_are_scan_friendly():
    rows = build_candidate_comparison_rows([_candidate()])

    assert rows == [
        {
            "Part": "CB1400-15",
            "Series": "CB1400",
            "Status": "PASS",
            "Worst use": "70%",
            "Limiting constraint": "Roll - Bottom (X,Y-axis) deflection",
            "Worst GT": "60%",
            "Worst deflection": "70%",
            "Static load": "50%",
        }
    ]


def test_candidate_comparison_rows_show_static_unknown():
    rows = build_candidate_comparison_rows([_candidate(static_rating=None)])

    assert rows[0]["Status"] == "PASS"
    assert rows[0]["Static load"] == "vendor check"


def test_load_case_rows_show_limit_use_and_margin():
    rows = build_load_case_rows(_candidate())

    assert rows[-1] == {
        "Case": "Roll - Bottom (X,Y-axis)",
        "Status": "PASS",
        "Limit use": "70%",
        "Margin": "30% remaining",
        "Binding": "deflection (clearance)",
        "GT [G]": 6.0,
        "dD [mm]": 28.0,
        "Load [kg]": 100.0,
    }


def test_load_case_rows_show_over_limit_margin_for_failures():
    candidate = _candidate(
        directions=[
            _direction("Comp - Bottom (Z-axis)", gt=12.0, delta=12.0),
            _direction("Comp - Wall (Y-axis)", gt=4.0, delta=10.0),
            _direction("Roll - Wall (X,Z-axis)", gt=3.0, delta=8.0),
            _direction("Roll - Bottom (X,Y-axis)", gt=6.0, delta=28.0),
        ]
    )

    rows = build_load_case_rows(candidate)

    assert rows[0]["Limit use"] == "120%"
    assert rows[0]["Margin"] == "20% over"
    assert rows[0]["Binding"] == "GT"
    assert rows[0]["Status"] == "FAIL"
