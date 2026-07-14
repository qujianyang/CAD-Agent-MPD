"""Parse the deterministic PASS/FAIL/ASK verdict envelope from model text."""

from __future__ import annotations

import json
import re
from typing import Any, Iterator


VALID_VERDICTS = {"PASS", "FAIL", "ASK"}
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _json_objects(text: str) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from fenced blocks and embedded prose.

    ``json.JSONDecoder`` is used instead of a brace regex so nested objects in
    ``key_numbers`` and ``units`` are handled correctly.
    """
    decoder = json.JSONDecoder()
    seen: set[str] = set()
    sources = [match.group(1) for match in _JSON_FENCE_RE.finditer(text)]
    sources.append(text)

    for source in sources:
        for start, char in enumerate(source):
            if char != "{":
                continue
            try:
                value, _end = decoder.raw_decode(source[start:])
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            marker = json.dumps(value, sort_keys=True, ensure_ascii=True)
            if marker not in seen:
                seen.add(marker)
                yield value


def _failure(message: str) -> dict[str, Any]:
    return {
        "verdict": None,
        "governing_check": None,
        "key_numbers": {},
        "units": {},
        "missing_inputs": [],
        "citations": [],
        "parse_error": message,
    }


def parse_verdict_envelope(text: str) -> dict[str, Any]:
    """Return one normalized envelope; malformed output records a parse error."""
    if not isinstance(text, str) or not text.strip():
        return _failure("Final response is empty.")

    candidates = [obj for obj in _json_objects(text) if "verdict" in obj]
    if not candidates:
        return _failure("No JSON object containing a verdict was found.")

    raw = candidates[-1]
    verdict = raw.get("verdict")
    if verdict is None:
        normalized_verdict = None
    elif isinstance(verdict, str) and verdict.strip().upper() in VALID_VERDICTS:
        normalized_verdict = verdict.strip().upper()
    else:
        return _failure("Verdict must be PASS, FAIL, ASK, or null for information-only questions.")

    key_numbers = raw.get("key_numbers", {})
    units = raw.get("units", {})
    missing_inputs = raw.get("missing_inputs", raw.get("missing_fields", []))
    citations = raw.get("citations", [])

    if not isinstance(key_numbers, dict):
        return _failure("key_numbers must be a JSON object.")
    if not isinstance(units, dict):
        return _failure("units must be a JSON object.")
    if not isinstance(missing_inputs, list) or not all(
        isinstance(item, str) for item in missing_inputs
    ):
        return _failure("missing_inputs must be a list of strings.")
    if not isinstance(citations, list) or not all(
        isinstance(item, str) for item in citations
    ):
        return _failure("citations must be a list of strings when present.")

    governing_check = raw.get("governing_check")
    if governing_check is not None and not isinstance(governing_check, str):
        return _failure("governing_check must be a string or null.")

    return {
        "verdict": normalized_verdict,
        "governing_check": governing_check,
        "key_numbers": key_numbers,
        "units": units,
        "missing_inputs": missing_inputs,
        "citations": citations,
        "parse_error": None,
    }
