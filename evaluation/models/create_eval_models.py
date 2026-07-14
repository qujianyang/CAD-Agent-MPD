"""Create and verify Ollama aliases with the frozen 8K evaluation context."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys

import requests


@dataclass(frozen=True)
class EvalModel:
    alias: str
    base: str


EVAL_MODELS = (
    EvalModel("cad-eval-qwen3-14b:8k", "qwen3:14b"),
    EvalModel("cad-eval-qwen35-9b:8k", "qwen3.5:9b"),
    EvalModel("cad-eval-gemma4-12b:8k", "gemma4:12b"),
)
PARAMETERS = {
    "num_ctx": 8192,
    "temperature": 0.0,
    "seed": 42,
    "num_predict": 2048,
    "top_k": 20,
    "top_p": 0.95,
    "repeat_penalty": 1.0,
}


def _native_api(openai_base_url: str) -> str:
    base = openai_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _parse_parameters(parameter_text: str) -> dict[str, str]:
    parsed = {}
    for line in parameter_text.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0]] = parts[1]
    return parsed


def create_models(base_url: str, timeout: float = 120.0) -> list[dict]:
    api = _native_api(base_url)
    verified = []
    for model in EVAL_MODELS:
        response = requests.post(
            f"{api}/api/create",
            json={
                "model": model.alias,
                "from": model.base,
                "parameters": PARAMETERS,
                "stream": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()

        shown = requests.post(
            f"{api}/api/show",
            json={"model": model.alias, "verbose": False},
            timeout=30,
        )
        shown.raise_for_status()
        details = shown.json()
        parameter_text = details.get("parameters", "")
        parsed_parameters = _parse_parameters(parameter_text)
        expected_parameters = {
            "num_ctx": "8192",
            "temperature": "0",
            "seed": "42",
            "num_predict": "2048",
            "top_k": "20",
            "top_p": "0.95",
            "repeat_penalty": "1",
        }
        for name, expected_value in expected_parameters.items():
            if parsed_parameters.get(name) != expected_value:
                raise RuntimeError(
                    f"{model.alias} does not expose {name}={expected_value}: "
                    f"{parameter_text!r}"
                )
        verified.append(
            {
                "alias": model.alias,
                "base": model.base,
                "parameters": parameter_text,
                "details": details.get("details", {}),
            }
        )
    return verified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    args = parser.parse_args(argv)
    try:
        verified = create_models(args.base_url)
    except requests.RequestException as exc:
        print(f"ERROR: Ollama request failed: {exc}", file=sys.stderr)
        return 1
    for item in verified:
        details = item["details"]
        print(
            f"[OK] {item['alias']} <- {item['base']} "
            f"{details.get('parameter_size', '?')} {details.get('quantization_level', '?')}"
        )
        print(f"     {item['parameters'].strip().replace(chr(10), ', ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
