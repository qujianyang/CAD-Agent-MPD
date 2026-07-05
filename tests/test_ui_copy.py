from ui_copy import (
    CLEAR_RESULT_LABEL,
    MAIN_TAB_LABELS,
    REVIEW_NEXT_LABEL,
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


def test_shock_result_has_actionable_stale_controls_and_no_floating_guide():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert UPDATE_RESULT_LABEL == "Update result"
    assert CLEAR_RESULT_LABEL == "Clear result"
    assert REVIEW_NEXT_LABEL == "Review next"
    assert "UPDATE_RESULT_LABEL" in app_source
    assert "CLEAR_RESULT_LABEL" in app_source
    assert "REVIEW_NEXT_LABEL" in app_source
    assert "render_floating_assistant(" not in app_source
