"""Small helper for selecting the chat-model provider from environment vars."""
from dataclasses import dataclass
import os
from typing import Mapping


DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    api_key_env: str


def resolve_llm_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Resolve the active chat-model provider.

    LLM_PROVIDER defaults to "nvidia" to preserve the existing behavior.
    Supported values: "nvidia", "openai" (alias: "chatgpt").
    """
    source = env if env is not None else os.environ
    provider = (source.get("LLM_PROVIDER") or "nvidia").strip().lower()
    if provider == "chatgpt":
        provider = "openai"

    if provider == "openai":
        return LLMConfig(
            provider="openai",
            model=(source.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL).strip(),
            api_key=(source.get("OPENAI_API_KEY") or "").strip(),
            api_key_env="OPENAI_API_KEY",
        )

    if provider == "nvidia":
        return LLMConfig(
            provider="nvidia",
            model=(source.get("NVIDIA_MODEL") or DEFAULT_NVIDIA_MODEL).strip(),
            api_key=(source.get("NVIDIA_API_KEY") or "").strip(),
            api_key_env="NVIDIA_API_KEY",
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider!r}. Use 'nvidia' or 'openai'."
    )
