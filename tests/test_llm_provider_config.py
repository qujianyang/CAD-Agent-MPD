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


if __name__ == "__main__":
    unittest.main()
