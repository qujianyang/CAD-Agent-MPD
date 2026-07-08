from ui_copy import (
    CLEAR_RESULT_LABEL,
    CLEARANCE_HELP_TEXT,
    MAIN_TAB_LABELS,
    REVIEW_NEXT_LABEL,
    ROAD_VIBRATION_LABEL,
    UPDATE_RESULT_LABEL,
)
from pathlib import Path


def test_main_tab_labels_are_plain_task_names():
    assert MAIN_TAB_LABELS == (
        "Shock selector",
        "CAD import",
        "Tie-down",
        "Mobility",
    )
    assert all(label.isascii() for label in MAIN_TAB_LABELS)


def test_app_copy_does_not_use_legacy_agent_branding():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "MCP Agent" not in app_source
    assert "Shock Mount Agent" not in app_source


def test_shock_selector_copy_avoids_clipped_or_decorative_labels():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Free gap to neighbouring equipment / rack wall per axis." not in app_source
    assert "🚚 Road-vibration check" not in app_source
    assert "🔬 Full physics report" not in app_source
    assert "💬 Ask the shock-isolation assistant" not in app_source


def test_app_uses_current_streamlit_width_api():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "use_container_width" not in app_source


def test_selection_objective_copy_is_clearance_first_without_balanced():
    app_source = Path("app.py").read_text(encoding="utf-8")
    catalog_source = Path("catalog.py").read_text(encoding="utf-8")
    agent_source = Path("agent.py").read_text(encoding="utf-8")

    assert '"Least movement / max clearance": "max_clearance"' in app_source
    assert '"Lowest transmitted shock": "best_isolation"' in app_source
    assert "Balanced (furthest from any limit)" not in app_source
    assert "balanced" not in catalog_source
    assert "balanced" not in agent_source


def test_shock_selector_has_custom_vendor_mode_without_excel_scope():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert '"Custom vendor data"' in app_source
    assert "analyze_custom_isolator(" in app_source
    assert "CustomIsolatorInput" in app_source
    assert "Stiffness source" in app_source
    assert "st.file_uploader" not in app_source


def test_shock_selector_has_interface_plate_scope_and_rack_presets():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Racks connected by common interface plate?" in app_source
    assert "Use total mass of all connected racks plus the interface plate." in app_source
    assert "Run each rack separately; do not combine masses." in app_source
    assert '"Single rack": (4, 2)' in app_source
    assert '"2-gang rack": (6, 2)' in app_source
    assert '"3-gang rack": (8, 2)' in app_source
    assert '"4-gang rack": (10, 2)' in app_source
    assert "Presets are starting points; override counts" in app_source


def test_clearance_help_text_explains_gap_scale_and_zero_bypass():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "allowed movement before contact" in CLEARANCE_HELP_TEXT
    assert "1 mm is usually too small" in CLEARANCE_HELP_TEXT
    assert "Use 0 to ignore" in CLEARANCE_HELP_TEXT
    assert "format_clearance_hint(" in app_source


def test_road_vibration_panel_explains_engineering_meaning():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert ROAD_VIBRATION_LABEL == "Road vibration check"
    assert "Road vibration: {vibration_state}" in app_source
    assert "reduces continuous road vibration" in app_source
    assert "Transfer ratio" in app_source
    assert "Below 1.0 means isolation" in app_source
    assert "Calculation details" in app_source
    assert "fn (vibration K)" not in app_source
    assert "g_rms in" not in app_source


def test_shock_result_has_actionable_stale_controls_and_floating_guide():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert UPDATE_RESULT_LABEL == "Update result"
    assert CLEAR_RESULT_LABEL == "Clear result"
    assert REVIEW_NEXT_LABEL == "Review next"
    assert "UPDATE_RESULT_LABEL" in app_source
    assert "CLEAR_RESULT_LABEL" in app_source
    assert "REVIEW_NEXT_LABEL" in app_source
    assert "from streamlit_float import float_init, float_css_helper" in app_source
    assert "def render_floating_assistant(" in app_source
    assert "ui_guide_shock" in app_source
    assert "ui_guide_tiedown" in app_source
    assert "ui_guide_mobility" in app_source
