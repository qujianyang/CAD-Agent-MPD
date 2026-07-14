"""Small helper for selecting the chat-model provider from environment vars."""
from dataclasses import dataclass
import os
from typing import Mapping


DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_OLLAMA_MODEL = "qwen3:14b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TOP_P = 1.0
DEFAULT_PRESENCE_PENALTY = 0.0


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    api_key_env: str
    base_url: str | None = None
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    seed: int | None = None
    reasoning_effort: str | None = None
    top_p: float = DEFAULT_TOP_P
    presence_penalty: float = DEFAULT_PRESENCE_PENALTY


def _inference_settings(source: Mapping[str, str]) -> dict:
    try:
        temperature = float(source.get("LLM_TEMPERATURE", DEFAULT_TEMPERATURE))
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM_TEMPERATURE must be a number.") from exc
    if temperature < 0:
        raise ValueError("LLM_TEMPERATURE cannot be negative.")

    try:
        top_p = float(source.get("LLM_TOP_P", DEFAULT_TOP_P))
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM_TOP_P must be a number between 0 and 1.") from exc
    if not 0 < top_p <= 1:
        raise ValueError("LLM_TOP_P must be greater than 0 and at most 1.")

    try:
        presence_penalty = float(
            source.get("LLM_PRESENCE_PENALTY", DEFAULT_PRESENCE_PENALTY)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM_PRESENCE_PENALTY must be a number.") from exc

    try:
        max_tokens = int(source.get("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS))
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM_MAX_TOKENS must be a positive integer.") from exc
    if max_tokens <= 0:
        raise ValueError("LLM_MAX_TOKENS must be a positive integer.")

    seed_text = str(source.get("LLM_SEED", "")).strip()
    try:
        seed = int(seed_text) if seed_text else None
    except ValueError as exc:
        raise ValueError("LLM_SEED must be an integer when set.") from exc

    reasoning_effort = str(source.get("LLM_REASONING_EFFORT", "")).strip().lower()
    if reasoning_effort and reasoning_effort not in {"none", "low", "medium", "high"}:
        raise ValueError(
            "LLM_REASONING_EFFORT must be one of none, low, medium, or high."
        )

    return {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": seed,
        "reasoning_effort": reasoning_effort or None,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
    }


def resolve_llm_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Resolve the active chat-model provider.

    LLM_PROVIDER defaults to "nvidia" to preserve the existing behavior.
    Supported values: "nvidia", "openai" (alias: "chatgpt"), "ollama".
    """
    source = env if env is not None else os.environ
    provider = (source.get("LLM_PROVIDER") or "nvidia").strip().lower()
    if provider == "chatgpt":
        provider = "openai"
    inference = _inference_settings(source)

    if provider == "openai":
        return LLMConfig(
            provider="openai",
            model=(source.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL).strip(),
            api_key=(source.get("OPENAI_API_KEY") or "").strip(),
            api_key_env="OPENAI_API_KEY",
            **inference,
        )

    if provider == "ollama":
        return LLMConfig(
            provider="ollama",
            model=(source.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL).strip(),
            # Ollama ignores the key, but the OpenAI-compatible client requires a
            # non-empty one. Use a dummy so _build_chat_model's guard passes.
            api_key=(source.get("OLLAMA_API_KEY") or "ollama").strip(),
            api_key_env="OLLAMA_API_KEY",
            base_url=(source.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).strip(),
            **inference,
        )

    if provider == "nvidia":
        return LLMConfig(
            provider="nvidia",
            model=(source.get("NVIDIA_MODEL") or DEFAULT_NVIDIA_MODEL).strip(),
            api_key=(source.get("NVIDIA_API_KEY") or "").strip(),
            api_key_env="NVIDIA_API_KEY",
            **inference,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider!r}. Use 'nvidia', 'openai', or 'ollama'."
    )
