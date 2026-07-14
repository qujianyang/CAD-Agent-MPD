"""Offline inspection of local ChatOpenAI request settings."""

import langchain_openai

from agent import _build_chat_model
from llm_config import resolve_llm_config


def test_local_model_receives_frozen_request_settings(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
    config = resolve_llm_config({
        "LLM_PROVIDER": "ollama",
        "OLLAMA_MODEL": "cad-eval-qwen35-9b:8k",
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "LLM_TEMPERATURE": "0",
        "LLM_MAX_TOKENS": "2048",
        "LLM_SEED": "42",
        "LLM_REASONING_EFFORT": "none",
        "LLM_TOP_P": "0.95",
        "LLM_PRESENCE_PENALTY": "0",
    })

    model = _build_chat_model(config)
    assert isinstance(model, FakeChatOpenAI)
    assert captured == {
        "model": "cad-eval-qwen35-9b:8k",
        "api_key": "ollama",
        "temperature": 0.0,
        "max_tokens": 2048,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "base_url": "http://localhost:11434/v1",
        "seed": 42,
        "reasoning_effort": "none",
    }
