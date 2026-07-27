"""Tests for the optional OpenAI shock-concept image layer."""

from __future__ import annotations

import base64
from dataclasses import replace
from types import SimpleNamespace

import pytest

from shock_analysis_context import ShockAnalysisSnapshot
from shock_concept_image import (
    build_concept_prompt,
    concept_evidence_rows,
    concept_cache_key,
    generate_concept_image,
)


def _snapshot(*, verdict: str = "PASS", wall_mounts: int = 4):
    return ShockAnalysisSnapshot(
        analysis_id="S-IMAGE01",
        mode="catalog_selection",
        verdict=verdict,
        mass_kg=850.0,
        bottom_mounts=6,
        wall_mounts=wall_mounts,
        input_shock_g=20.0,
        pulse_duration_ms=11.0,
        pulse_shape="sawtooth",
        transmitted_g_limit=10.0,
        selected_part="CB1400-15",
        selected_series="CB1400",
        governing_case="Compression Bottom",
        governing_constraint="transmitted_g",
        governing_use_pct=63,
        worst_transmitted_g=6.3,
        worst_movement_mm=18.9,
        static_load_daN=141.7,
        static_rating_daN=250.0,
        validation_level=None,
        load_cases=(),
        alternatives=(),
        warnings=(),
    )


def test_prompt_is_explanatory_and_excludes_exact_vendor_details():
    prompt = build_concept_prompt(_snapshot())

    assert "upper wall-mounted helical wire-rope isolators" in prompt
    assert "visibly smaller blue arrows" in prompt
    assert "VISUAL PURPOSE: Shock attenuation" in prompt
    assert "not a manufacturing drawing" in prompt
    assert "vertical twisted-rope columns" in prompt
    assert "CB1400-15" not in prompt
    assert "850" not in prompt
    assert "20 G" not in prompt


def test_failed_analysis_prompt_does_not_imply_success():
    prompt = build_concept_prompt(_snapshot(verdict="FAIL"))

    assert "did not pass" in prompt
    assert "Do not imply" in prompt


def test_cache_key_changes_with_analysis_or_quality():
    draft = concept_cache_key(_snapshot(), quality="low")
    presentation = concept_cache_key(_snapshot(), quality="medium")
    changed_analysis = concept_cache_key(
        replace(_snapshot(), analysis_id="S-IMAGE02"),
        quality="low",
    )
    custom_direction = concept_cache_key(
        _snapshot(),
        quality="low",
        visual_instructions="Use an exploded view.",
    )
    with_reference = concept_cache_key(
        _snapshot(),
        quality="low",
        reference_image_data=b"reference",
    )
    arrangement = concept_cache_key(
        _snapshot(),
        quality="low",
        visual_purpose="mounting_arrangement",
    )
    side_section = concept_cache_key(
        _snapshot(),
        quality="low",
        viewpoint="side_section",
    )

    assert draft != presentation
    assert draft != changed_analysis
    assert draft != custom_direction
    assert draft != with_reference
    assert draft != arrangement
    assert draft != side_section


def test_prompt_includes_user_direction_and_reference_instruction():
    prompt = build_concept_prompt(
        _snapshot(),
        visual_instructions="Use a flat side view with a pale blue background.",
        has_reference_image=True,
    )

    assert "USER VISUAL DIRECTION" in prompt
    assert "flat side view" in prompt
    assert "source of truth" in prompt


def test_prompt_modes_and_viewpoints_have_distinct_mechanical_direction():
    arrangement = build_concept_prompt(
        _snapshot(),
        visual_purpose="mounting_arrangement",
        viewpoint="side_section",
    )
    mechanism = build_concept_prompt(
        _snapshot(),
        visual_purpose="wire_rope_mechanism",
        viewpoint="close_up_detail",
    )

    assert "VISUAL PURPOSE: Mounting arrangement" in arrangement
    assert "orthographic side section" in arrangement
    assert "never loose restraint cables" in arrangement
    assert "VISUAL PURPOSE: Wire-rope mechanism" in mechanism
    assert "ghosted loaded position" in mechanism
    assert "close-up engineering detail" in mechanism


def test_prompt_rejects_unknown_purpose_or_viewpoint():
    with pytest.raises(ValueError, match="visual purpose"):
        build_concept_prompt(_snapshot(), visual_purpose="unknown")
    with pytest.raises(ValueError, match="viewpoint"):
        build_concept_prompt(_snapshot(), viewpoint="unknown")


def test_evidence_rows_keep_image_separate_from_qualification():
    generic_rows = concept_evidence_rows(
        _snapshot(),
        has_reference_image=False,
    )
    reference_rows = concept_evidence_rows(
        _snapshot(),
        has_reference_image=True,
    )

    assert generic_rows[0][1] == "PASS"
    assert generic_rows[2][1] == "GENERIC"
    assert reference_rows[2][1] == "REFERENCE-BASED"
    assert any(row[1] == "PENDING" for row in generic_rows)
    assert any(row[1] == "SEPARATE CHECK" for row in generic_rows)
    assert any(row[1] == "NOT ESTABLISHED" for row in generic_rows)


def test_generate_decodes_image_and_uses_expected_api_parameters():
    calls = []

    class FakeImages:
        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            payload = base64.b64encode(b"fake-webp").decode("ascii")
            return SimpleNamespace(data=[SimpleNamespace(b64_json=payload)])

    client = SimpleNamespace(images=FakeImages())
    result = generate_concept_image(
        _snapshot(),
        api_key="test-key",
        quality="medium",
        visual_purpose="mounting_arrangement",
        viewpoint="side_section",
        client=client,
    )

    assert result.data == b"fake-webp"
    assert result.media_type == "image/webp"
    assert result.quality == "medium"
    assert result.used_reference_image is False
    assert result.visual_purpose == "mounting_arrangement"
    assert result.viewpoint == "side_section"
    assert calls[0][0] == "generate"
    assert calls[0][1]["model"] == "gpt-image-2"
    assert calls[0][1]["size"] == "1536x1024"
    assert calls[0][1]["output_format"] == "webp"
    assert calls[0][1]["output_compression"] == 85
    assert "Mounting arrangement" in calls[0][1]["prompt"]
    assert "orthographic side section" in calls[0][1]["prompt"]


def test_generate_uses_edit_endpoint_when_reference_is_supplied():
    calls = []

    class FakeImages:
        def edit(self, **kwargs):
            calls.append(("edit", kwargs))
            payload = base64.b64encode(b"edited-webp").decode("ascii")
            return SimpleNamespace(data=[SimpleNamespace(b64_json=payload)])

        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            raise AssertionError("generate should not be used with a reference")

    reference = ("isolator.png", b"reference-bytes", "image/png")
    result = generate_concept_image(
        _snapshot(),
        api_key="test-key",
        visual_instructions="Use a side view.",
        reference_image=reference,
        client=SimpleNamespace(images=FakeImages()),
    )

    assert result.data == b"edited-webp"
    assert result.used_reference_image is True
    assert calls[0][0] == "edit"
    assert calls[0][1]["image"] == reference
    assert "side view" in calls[0][1]["prompt"]


def test_generate_requires_openai_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        generate_concept_image(_snapshot(), api_key="")
