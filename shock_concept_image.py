"""Generate explanatory shock-isolation artwork from a verified snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
from typing import Any

from shock_analysis_context import ShockAnalysisSnapshot


DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_IMAGE_SIZE = "1536x1024"
DEFAULT_IMAGE_FORMAT = "webp"
PROMPT_VERSION = "shock-concept-v3"
MAX_VISUAL_INSTRUCTIONS_CHARS = 1500

QUALITY_OPTIONS = {
    "Draft": "low",
    "Presentation": "medium",
}

VISUAL_PURPOSE_OPTIONS = {
    "Shock attenuation": "shock_attenuation",
    "Mounting arrangement": "mounting_arrangement",
    "Wire-rope mechanism": "wire_rope_mechanism",
}

VIEWPOINT_OPTIONS = {
    "Three-quarter cutaway": "three_quarter_cutaway",
    "Side section": "side_section",
    "Close-up detail": "close_up_detail",
}

VISUAL_PURPOSE_HINTS = {
    "shock_attenuation": (
        "Shows the shock path from the support structure through the isolators "
        "to the protected rack."
    ),
    "mounting_arrangement": (
        "Shows the relationship between the rack, bottom isolators and optional "
        "upper wall stabilizers. Exact coordinates remain in the mount drawing."
    ),
    "wire_rope_mechanism": (
        "Shows how helical wire-rope loops deform between two clamp bars. It is "
        "not a material or nonlinear-performance simulation."
    ),
}

_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


@dataclass(frozen=True)
class GeneratedConceptImage:
    """Image bytes and the metadata needed to render or download them."""

    data: bytes
    media_type: str
    file_extension: str
    model: str
    quality: str
    size: str
    cache_key: str
    used_reference_image: bool
    visual_purpose: str
    viewpoint: str


def concept_evidence_rows(
    snapshot: ShockAnalysisSnapshot,
    *,
    has_reference_image: bool,
) -> tuple[tuple[str, str, str], ...]:
    """Return deterministic evidence boundaries shown beside the artwork."""
    appearance_status = "REFERENCE-BASED" if has_reference_image else "GENERIC"
    appearance_detail = (
        "Physical appearance follows the uploaded approved reference."
        if has_reference_image
        else "Physical appearance is a generic helical wire-rope concept."
    )
    return (
        (
            "Shock calculation",
            snapshot.verdict,
            f"Deterministic Analysis {snapshot.analysis_id}.",
        ),
        (
            "Mount arrangement",
            "CONCEPTUAL",
            (
                f"{snapshot.bottom_mounts} bottom + {snapshot.wall_mounts} wall "
                "isolators; exact coordinates are not encoded in the image."
            ),
        ),
        ("Physical appearance", appearance_status, appearance_detail),
        (
            "Supplier confirmation",
            "PENDING",
            "Part, interfaces, nonlinear curves and installation remain unapproved.",
        ),
        (
            "Random vibration",
            "SEPARATE CHECK",
            "A shock illustration does not demonstrate vibration compliance.",
        ),
        (
            "Physical test / road trial",
            "NOT ESTABLISHED",
            "The generated image is not test or qualification evidence.",
        ),
    )


def build_concept_prompt(
    snapshot: ShockAnalysisSnapshot,
    *,
    visual_purpose: str = "shock_attenuation",
    viewpoint: str = "three_quarter_cutaway",
    visual_instructions: str = "",
    has_reference_image: bool = False,
) -> str:
    """Build a controlled prompt without exposing CAD files or vendor documents."""
    if visual_purpose not in VISUAL_PURPOSE_OPTIONS.values():
        raise ValueError(f"Unsupported visual purpose: {visual_purpose}")
    if viewpoint not in VIEWPOINT_OPTIONS.values():
        raise ValueError(f"Unsupported viewpoint: {viewpoint}")

    visual_instructions = visual_instructions.strip()
    if len(visual_instructions) > MAX_VISUAL_INSTRUCTIONS_CHARS:
        raise ValueError(
            "Visual instructions must be "
            f"{MAX_VISUAL_INSTRUCTIONS_CHARS} characters or fewer."
        )

    wall_mount_direction = (
        "Include representative upper wall-mounted helical wire-rope isolators "
        "as well as bottom isolators."
        if snapshot.wall_mounts
        else "Show bottom wire-rope isolators only."
    )
    if snapshot.verdict == "PASS":
        result_direction = (
            "The verified calculation passed. Show the input shock as a strong "
            "red arrow entering through the supporting vehicle structure and the "
            "transmitted response as visibly smaller blue arrows reaching the "
            "protected rack."
        )
    else:
        result_direction = (
            "The verified calculation did not pass. Show that substantial shock "
            "still reaches the rack, using a red warning accent. Do not imply that "
            "the equipment is adequately protected."
        )

    purpose_direction = {
        "shock_attenuation": (
            "VISUAL PURPOSE: Shock attenuation. Use one coherent scene. Show the "
            "load path from the supporting vehicle structure, through correctly "
            "oriented wire-rope isolators, into the protected equipment rack. "
            "Make the difference between input and transmitted response visually "
            "obvious through arrow size and colour, without written labels."
        ),
        "mounting_arrangement": (
            "VISUAL PURPOSE: Mounting arrangement. Prioritize a plausible generic "
            "rack installation. Bottom isolators must lie between the rack base "
            "and support frame, with their two clamp bars attached to opposing "
            "structures. Any wall stabilizers must be complete helical wire-rope "
            "isolator units between the upper rack and wall frame, never loose "
            "restraint cables. Do not claim exact positions or dimensions."
        ),
        "wire_rope_mechanism": (
            "VISUAL PURPOSE: Wire-rope mechanism. Prioritize one large, mechanically "
            "credible isolator detail. Clearly show a continuous multi-strand "
            "steel cable forming repeated helical loops between two parallel "
            "metal clamp bars, plus a subtle ghosted loaded position that shows "
            "compression or shear deformation. Keep the rack secondary."
        ),
    }[visual_purpose]
    viewpoint_direction = {
        "three_quarter_cutaway": (
            "VIEWPOINT: three-quarter technical cutaway with restrained depth and "
            "all important interfaces visible."
        ),
        "side_section": (
            "VIEWPOINT: clean orthographic side section with minimal perspective "
            "distortion and a clearly readable load path."
        ),
        "close_up_detail": (
            "VIEWPOINT: close-up engineering detail focused on isolator construction "
            "and attachment interfaces, with only enough rack structure for context."
        ),
    }[viewpoint]
    reference_direction = (
        "Use the uploaded reference image as the source of truth for the "
        "isolator's physical construction, cable-loop orientation and clamp-bar "
        "geometry. Preserve those mechanical features more strongly than stylistic "
        "instructions. Create a new explanatory scene; do not merely reproduce "
        "the reference background or any text visible in it."
        if has_reference_image
        else (
            "No approved physical reference is supplied. Use a generic helical "
            "wire-rope isolator and avoid vendor-specific geometry."
        )
    )
    user_direction = (
        "USER VISUAL DIRECTION: "
        f"{visual_instructions} "
        if visual_instructions
        else ""
    )

    return (
        "Create a clean, professional technical training illustration that "
        "explains shock isolation for a generic equipment rack mounted to a "
        "vehicle or support frame. Keep the rack, support structure and helical "
        "wire-rope isolators easy to distinguish. "
        f"{purpose_direction} {viewpoint_direction} {wall_mount_direction} "
        f"{result_direction} {reference_direction} "
        f"{user_direction}"
        "MECHANICAL APPEARANCE REQUIREMENT: Every isolator must be recognizable "
        "as a true helical wire-rope isolator: one continuous steel wire rope "
        "forms several circular or elliptical loops captured between two parallel "
        "metal clamp bars. Each complete unit must attach one clamp bar to the rack "
        "and the opposing clamp bar to the support structure. Do not depict coil "
        "springs, vertical twisted-rope columns, loose cables, guy wires, eye "
        "bolts or cable tie-downs as isolators. "
        "Show the wire ropes deforming conceptually to absorb energy. Keep the "
        "mechanical arrangement plausible, restrained and suitable for an "
        "engineering client presentation. Use a white or very light neutral "
        "background with red for input shock and blue for transmitted response. "
        "NON-NEGOTIABLE OUTPUT RULES: Do not include written text, numbers, "
        "dimensions, equations, logos, "
        "brand names, part numbers, certification marks or test claims. This is "
        "an explanatory concept illustration, not a manufacturing drawing; exact "
        "mount coordinates and quantities are shown separately by the "
        "deterministic engineering interface."
    )


def concept_cache_key(
    snapshot: ShockAnalysisSnapshot,
    *,
    model: str = DEFAULT_IMAGE_MODEL,
    quality: str = "low",
    size: str = DEFAULT_IMAGE_SIZE,
    output_format: str = DEFAULT_IMAGE_FORMAT,
    visual_purpose: str = "shock_attenuation",
    viewpoint: str = "three_quarter_cutaway",
    visual_instructions: str = "",
    reference_image_data: bytes | None = None,
) -> str:
    """Return a stable cache key for one analysis and render configuration."""
    reference_digest = (
        hashlib.sha256(reference_image_data).hexdigest()
        if reference_image_data
        else "no-reference"
    )
    payload = "|".join(
        (
            PROMPT_VERSION,
            snapshot.analysis_id,
            snapshot.verdict,
            str(snapshot.wall_mounts),
            model,
            quality,
            size,
            output_format,
            visual_purpose,
            viewpoint,
            visual_instructions.strip(),
            reference_digest,
        )
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def generate_concept_image(
    snapshot: ShockAnalysisSnapshot,
    *,
    api_key: str,
    model: str = DEFAULT_IMAGE_MODEL,
    quality: str = "low",
    size: str = DEFAULT_IMAGE_SIZE,
    output_format: str = DEFAULT_IMAGE_FORMAT,
    visual_purpose: str = "shock_attenuation",
    viewpoint: str = "three_quarter_cutaway",
    visual_instructions: str = "",
    reference_image: tuple[str, bytes, str] | None = None,
    client: Any = None,
) -> GeneratedConceptImage:
    """Call the OpenAI Image API and decode its base64 image response."""
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is required for concept-image generation.")
    if quality not in {"low", "medium", "high", "auto"}:
        raise ValueError(f"Unsupported image quality: {quality}")
    if output_format not in _MEDIA_TYPES:
        raise ValueError(f"Unsupported image format: {output_format}")

    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=120.0)

    request = {
        "model": model,
        "prompt": build_concept_prompt(
            snapshot,
            visual_purpose=visual_purpose,
            viewpoint=viewpoint,
            visual_instructions=visual_instructions,
            has_reference_image=reference_image is not None,
        ),
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "output_compression": 85,
    }
    if reference_image is not None:
        response = client.images.edit(
            image=reference_image,
            **request,
        )
    else:
        response = client.images.generate(**request)
    if not response.data:
        raise RuntimeError("The image service returned no image.")

    encoded = getattr(response.data[0], "b64_json", None)
    if not encoded:
        raise RuntimeError("The image service returned no image data.")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("The image service returned invalid image data.") from exc

    return GeneratedConceptImage(
        data=image_bytes,
        media_type=_MEDIA_TYPES[output_format],
        file_extension=output_format,
        model=model,
        quality=quality,
        size=size,
        cache_key=concept_cache_key(
            snapshot,
            model=model,
            quality=quality,
            size=size,
            output_format=output_format,
            visual_purpose=visual_purpose,
            viewpoint=viewpoint,
            visual_instructions=visual_instructions,
            reference_image_data=(
                reference_image[1] if reference_image is not None else None
            ),
        ),
        used_reference_image=reference_image is not None,
        visual_purpose=visual_purpose,
        viewpoint=viewpoint,
    )
