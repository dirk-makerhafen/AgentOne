import importlib.util
from pathlib import Path

from django.test import TestCase

from registry.loader.load_providers import load_providers_manifest
from server.models.providers.api_provider import ApiProvider

# pylint: disable=protected-access  # testing the internal routing helper

CALL_LLM_PATH = (Path(__file__).resolve().parent.parent.parent / ".agentone" / "scripts" / "core" / "call_llm.py")


def _load_call_llm():
    spec = importlib.util.spec_from_file_location("agentone_call_llm_under_test", CALL_LLM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiteLLMRoutingTest(TestCase):
    """Routing from an ``ApiProvider`` to a LiteLLM model string."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call_llm = _load_call_llm()

    def test_native_prefix_provider(self):
        provider = ApiProvider(name="Groq", litellm_prefix="groq")
        self.assertEqual(
            self.call_llm._get_litellm_model_name(provider, "moonshotai/kimi-k2-instruct"),
            "groq/moonshotai/kimi-k2-instruct",
        )

    def test_gemini_prefix(self):
        provider = ApiProvider(name="Google", litellm_prefix="gemini")
        self.assertEqual(
            self.call_llm._get_litellm_model_name(provider, "gemini-3.6-flash"),
            "gemini/gemini-3.6-flash",
        )

    def test_openai_compatible_fallback(self):
        provider = ApiProvider(name="Nvidia", url="https://integrate.api.nvidia.com/v1")
        self.assertEqual(
            self.call_llm._get_litellm_model_name(provider, "z-ai/glm-5.2"),
            "openai/z-ai/glm-5.2",
        )

    def test_blank_prefix_is_openai_compatible(self):
        provider = ApiProvider(name="Ollama Cloud", litellm_prefix="   ")
        self.assertEqual(
            self.call_llm._get_litellm_model_name(provider, "minimax-m3"),
            "openai/minimax-m3",
        )

    def test_no_provider_falls_back_to_openai(self):
        self.assertEqual(
            self.call_llm._get_litellm_model_name(None, "some-model"),
            "openai/some-model",
        )


class LiteLLMPrefixLoadingTest(TestCase):
    """The loader persists ``litellm_prefix`` from the provider manifest."""

    def test_prefix_persisted_from_manifest(self):
        manifest = Path("/tmp/opencode-test-prefix.yaml")
        manifest.write_text(
            """
providers:
  - name: Prefix Test
    url: https://example.com/v1
    litellm_prefix: groq
  - name: Compat Test
    url: https://example.com/v2
""",
            encoding="utf-8",
        )
        try:
            details = []
            load_providers_manifest(manifest, details)
            self.assertEqual(ApiProvider.objects.get(name="Prefix Test").litellm_prefix, "groq")
            self.assertEqual(ApiProvider.objects.get(name="Compat Test").litellm_prefix, "")
        finally:
            manifest.unlink(missing_ok=True)

    def test_prefix_updated_when_manifest_changes(self):
        manifest = Path("/tmp/opencode-test-prefix-update.yaml")
        manifest.write_text(
            'providers:\n  - name: Prefix Test\n    url: https://example.com/v1\n    litellm_prefix: gemini\n',
            encoding="utf-8",
        )
        try:
            details = []
            load_providers_manifest(manifest, details)
            provider = ApiProvider.objects.get(name="Prefix Test")
            self.assertEqual(provider.litellm_prefix, "gemini")
            manifest.write_text(
                'providers:\n  - name: Prefix Test\n    url: https://example.com/v1\n',
                encoding="utf-8",
            )
            load_providers_manifest(manifest, details)
            provider.refresh_from_db()
            self.assertEqual(provider.litellm_prefix, "")
        finally:
            manifest.unlink(missing_ok=True)