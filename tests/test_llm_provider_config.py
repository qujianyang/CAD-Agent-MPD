import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_config import resolve_llm_config


class LLMProviderConfigTests(unittest.TestCase):
    def test_openai_provider_uses_openai_key_and_demo_default_model(self):
        cfg = resolve_llm_config({
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test",
        })

        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-5.4-mini")
        self.assertEqual(cfg.api_key, "sk-test")
        self.assertEqual(cfg.api_key_env, "OPENAI_API_KEY")

    def test_nvidia_provider_remains_default(self):
        cfg = resolve_llm_config({
            "NVIDIA_API_KEY": "nvapi-test",
        })

        self.assertEqual(cfg.provider, "nvidia")
        self.assertEqual(cfg.model, "meta/llama-3.1-70b-instruct")
        self.assertEqual(cfg.api_key, "nvapi-test")
        self.assertEqual(cfg.api_key_env, "NVIDIA_API_KEY")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LLM_PROVIDER"):
            resolve_llm_config({"LLM_PROVIDER": "bad-provider"})

    def test_inference_settings_are_parsed_for_local_evaluation(self):
        cfg = resolve_llm_config({
            "LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "cad-eval-qwen35-9b:8k",
            "LLM_TEMPERATURE": "0",
            "LLM_MAX_TOKENS": "2048",
            "LLM_SEED": "42",
            "LLM_REASONING_EFFORT": "none",
            "LLM_TOP_P": "0.95",
            "LLM_PRESENCE_PENALTY": "0",
        })

        self.assertEqual(cfg.temperature, 0.0)
        self.assertEqual(cfg.max_tokens, 2048)
        self.assertEqual(cfg.seed, 42)
        self.assertEqual(cfg.reasoning_effort, "none")
        self.assertEqual(cfg.top_p, 0.95)
        self.assertEqual(cfg.presence_penalty, 0.0)

    def test_invalid_inference_setting_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LLM_MAX_TOKENS"):
            resolve_llm_config({
                "LLM_PROVIDER": "ollama",
                "LLM_MAX_TOKENS": "zero",
            })


if __name__ == "__main__":
    unittest.main()
