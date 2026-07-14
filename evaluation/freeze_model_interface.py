"""Capture the frozen local model, prompts, tool schemas, and source hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import requests

from evaluation.harness.systems import SYSTEMS


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "evaluation" / "artifacts" / "model_interface_manifest.json"
SELECTED_ALIAS = "cad-eval-qwen35-9b:8k"
SELECTED_ALIAS_DIGEST = (
    "41877dcbd4e07e5c9c40f5ab7968bc651674d83801a171cfd6b0684d13701910"
)
EXPECTED_PARAMETERS = {
    "num_ctx": "8192",
    "temperature": "0",
    "seed": "42",
    "num_predict": "2048",
    "top_k": "20",
    "top_p": "0.95",
    "repeat_penalty": "1",
}
SOURCE_FILES = (
    "agent.py",
    "llm_config.py",
    "catalog.py",
    "physics_engine.py",
    "tiedown_engine.py",
    "tiedown_tools.py",
    "fastener_catalog.py",
    "mobility_engine.py",
    "mobility_tools.py",
    "evaluation/models/qwen35-9b.Modelfile",
    "evaluation/harness/systems.py",
    "evaluation/harness/runner.py",
    "evaluation/harness/verdict.py",
    "evaluation/scoring/metrics.py",
    "evaluation/scoring/scorer.py",
)
DOMAINS = ("shock_mount", "tiedown", "mobility")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _file_hash(relative_path: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Required freeze source is missing: {relative_path}")
    return {
        "path": relative_path,
        "sha256": _sha256_bytes(path.read_bytes()),
        "size_bytes": path.stat().st_size,
    }


def _tool_schema(tool: object) -> dict[str, Any]:
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        schema: dict[str, Any] = {}
    elif hasattr(args_schema, "model_json_schema"):
        schema = args_schema.model_json_schema()
    elif hasattr(args_schema, "schema"):
        schema = args_schema.schema()
    else:
        raise TypeError(f"Cannot serialize args schema for {getattr(tool, 'name', tool)!r}")
    return {
        "name": str(getattr(tool, "name", getattr(tool, "__name__", ""))),
        "description": str(getattr(tool, "description", "")),
        "args_schema": schema,
    }


def _domain_records() -> dict[str, Any]:
    import agent

    records: dict[str, Any] = {}
    for domain in DOMAINS:
        config = agent.DOMAINS[domain]
        prompt = str(config["prompt"])
        tools = [_tool_schema(tool) for tool in config["tools"]]
        records[domain] = {
            "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "prompt_length_chars": len(prompt),
            "tool_schema_sha256": _sha256_json(tools),
            "tools": tools,
        }
    return records


def _core_system_records() -> dict[str, dict[str, Any]]:
    core = {system_id: SYSTEMS[system_id].public_record() for system_id in "BCD"}
    controlled_fields = (
        "provider",
        "model",
        "base_model",
        "base_url",
        "context_length",
        "temperature",
        "max_tokens",
        "seed",
        "reasoning_effort",
        "top_p",
        "presence_penalty",
    )
    for field in controlled_fields:
        values = {record[field] for record in core.values()}
        if len(values) != 1:
            raise AssertionError(f"B/C/D differ unexpectedly for {field}: {values}")
    expected_variants = {
        "B": (False, False),
        "C": (True, False),
        "D": (True, True),
    }
    actual_variants = {
        system_id: (record["tools"], record["rag"])
        for system_id, record in core.items()
    }
    if actual_variants != expected_variants:
        raise AssertionError(f"Unexpected B/C/D variants: {actual_variants}")
    if {record["model"] for record in core.values()} != {SELECTED_ALIAS}:
        raise AssertionError("B/C/D are not all using the selected local alias")
    return core


def _parse_parameters(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0]] = parts[1]
    return parsed


def _ollama_record(base_url: str) -> dict[str, Any]:
    native_url = base_url.rstrip("/")
    if native_url.endswith("/v1"):
        native_url = native_url[:-3]

    tags_response = requests.get(f"{native_url}/api/tags", timeout=30)
    tags_response.raise_for_status()
    models = tags_response.json().get("models", [])
    selected = next(
        (item for item in models if item.get("name") == SELECTED_ALIAS),
        None,
    )
    if selected is None:
        raise RuntimeError(f"Ollama alias is not installed: {SELECTED_ALIAS}")
    if selected.get("digest") != SELECTED_ALIAS_DIGEST:
        raise RuntimeError(
            f"Alias digest changed: {selected.get('digest')} != {SELECTED_ALIAS_DIGEST}"
        )

    show_response = requests.post(
        f"{native_url}/api/show",
        json={"model": SELECTED_ALIAS, "verbose": False},
        timeout=30,
    )
    show_response.raise_for_status()
    shown = show_response.json()
    parameters = _parse_parameters(str(shown.get("parameters", "")))
    for name, expected in EXPECTED_PARAMETERS.items():
        if parameters.get(name) != expected:
            raise RuntimeError(
                f"Ollama alias parameter changed: {name}={parameters.get(name)!r}, "
                f"expected {expected!r}"
            )
    return {
        "version_endpoint": native_url,
        "alias": SELECTED_ALIAS,
        "digest": selected["digest"],
        "size_bytes": selected.get("size"),
        "details": selected.get("details", {}),
        "parameters": parameters,
    }


def build_manifest(base_url: str, verify_ollama: bool = True) -> dict[str, Any]:
    manifest = {
        "manifest_version": "model-interface-v1",
        "recorded_date": "2026-07-13",
        "selected_model": {
            "base_model": "qwen3.5:9b",
            "evaluation_alias": SELECTED_ALIAS,
            "alias_digest": SELECTED_ALIAS_DIGEST,
        },
        "core_systems": _core_system_records(),
        "domains": _domain_records(),
        "source_files": [_file_hash(path) for path in SOURCE_FILES],
    }
    manifest["ollama"] = (
        _ollama_record(base_url)
        if verify_ollama
        else {"verification": "skipped"}
    )
    manifest["manifest_content_sha256"] = _sha256_json(manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-ollama", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_manifest(args.base_url, verify_ollama=not args.skip_ollama)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] Wrote model/interface manifest to {args.out}")
    print(f"[OK] Manifest SHA-256: {manifest['manifest_content_sha256']}")
    print(f"[OK] Frozen domains: {', '.join(manifest['domains'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
