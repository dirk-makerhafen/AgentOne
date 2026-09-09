"""Tests for the research-frontmatter provider/model loader.

Covers ``load_providers_dir``: provider upsert by filename slug,
nested-limits mapping, model-card join, single-int rank (incl. estimated),
gate-row skip, rename-without-dupe, and disable-missing semantics.
"""
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase

from registry.loader.load_providers import load_providers_dir
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


PROVIDER_MD = """\
---
name: Test Provider
url: "https://example.com"
api_base: "https://example.com/api/v1"
api_key_url: "https://example.com/keys"
setup_instructions: |
  Sign up and create a key.
default_api_key: public
limits:
  requests:
    minute: 20
    day: 1000
---
Body prose.
"""

CARD_MD = """\
---
name: Test Model
developer: TestDev
canonical_id: testdev/test-model
family: test
leaderboard_id: test-model
leaderboard_rank: 42
context_window: 131072
max_output_tokens: 8192
reasoning: true
tool_call: true
modalities:
  input: [text, image]
  output: [text]
providers:
  - name: Test Provider
    file: test-provider
    model_id: test-model-free
    conditions: "Free lane, no card"
    verified: "2026-09-06"
---
Body prose.
"""


class ProviderMdLoaderTest(TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.providers = self._tmp / "providers"
        self.models = self._tmp / "models"
        self.providers.mkdir()
        self.models.mkdir()

    def _write(self, folder: Path, name: str, content: str) -> None:
        (folder / name).write_text(content, encoding="utf-8")

    def _load(self, **kwargs):
        details = []
        count = load_providers_dir(self.providers, self.models, details, **kwargs)
        return count, details

    def test_provider_upsert_by_slug(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        count, _ = self._load()
        self.assertEqual(count, 1)
        provider = ApiProvider.objects.get(slug="test-provider")
        self.assertEqual(provider.name, "Test Provider")
        self.assertEqual(provider.url, "https://example.com/api/v1")
        self.assertEqual(provider.limit_request_per_minute, 20)
        self.assertEqual(provider.limit_request_per_day, 1000)
        self.assertEqual(provider.data.get("default_api_key"), "public")
        self.assertTrue(provider.enabled)

    def test_rename_updates_without_dupe(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._load()
        renamed = PROVIDER_MD.replace("name: Test Provider", "name: Renamed Provider")
        self._write(self.providers, "test-provider.md", renamed)
        self._load()
        self.assertEqual(ApiProvider.objects.filter(slug="test-provider").count(), 1)
        self.assertEqual(ApiProvider.objects.get(slug="test-provider").name, "Renamed Provider")

    def test_homepage_url_without_api_base_skips(self):
        self._write(self.providers, "vague.md", "---\nname: Vague\nurl: \"https://vague.com\"\n---\nBody.\n")
        self._load()
        self.assertFalse(ApiProvider.objects.filter(slug="vague").exists())

    def test_card_join_creates_model_with_int_rank(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._write(self.models, "test-model.md", CARD_MD)
        self._load()
        model = AiModel.objects.get(provider_model_id="test-model-free")
        self.assertEqual(model.name, "Test Model")
        self.assertEqual(model.developer, "TestDev")
        self.assertEqual(model.canonical_id, "testdev/test-model")
        self.assertEqual(model.leaderboard_id, "test-model")
        self.assertEqual(model.leaderboard_rank, 42)
        self.assertFalse(model.leaderboard_rank_is_estimate)
        self.assertTrue(model.supports_reasoning)
        self.assertTrue(model.supports_tool_call)
        self.assertTrue(model.vision)
        self.assertEqual(model.context_length, 131072)
        self.assertEqual(model.max_response_tokens, 8192)
        self.assertEqual(model.data.get("conditions"), "Free lane, no card")

    def test_estimated_rank_stored_as_int_with_flag(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        card = CARD_MD.replace("leaderboard_rank: 42", "leaderboard_rank_estimated: \"~25\"")
        self._write(self.models, "test-model.md", card)
        self._load()
        model = AiModel.objects.get(provider_model_id="test-model-free")
        self.assertEqual(model.leaderboard_rank, 25)
        self.assertTrue(model.leaderboard_rank_is_estimate)

    def test_gated_row_skipped(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        card = CARD_MD.replace(
            "    verified: \"2026-09-06\"",
            "    verified: \"2026-09-06\"\n    gate: \"requires paid billing\"",
        )
        self._write(self.models, "test-model.md", card)
        _, details = self._load()
        self.assertFalse(AiModel.objects.filter(provider_model_id="test-model-free").exists())
        self.assertTrue(any(d["action"] == "skipped (payment-gated)" for d in details))

    def test_unknown_provider_file_skipped(self):
        self._write(self.models, "test-model.md", CARD_MD)
        _, details = self._load()
        self.assertFalse(AiModel.objects.exists())
        self.assertTrue(any(d["action"] == "skipped (unknown provider file)" for d in details))

    def test_disable_missing(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._write(self.models, "test-model.md", CARD_MD)
        self._load()
        (self.providers / "test-provider.md").unlink()
        (self.models / "test-model.md").unlink()
        _, details = self._load(disable_missing=True)
        provider = ApiProvider.objects.get(slug="test-provider")
        self.assertFalse(provider.enabled)
        model = AiModel.objects.get(provider_model_id="test-model-free")
        self.assertFalse(model.enabled)
        actions = [d["action"] for d in details]
        self.assertIn("disabled (no file)", actions)
        self.assertIn("disabled (no card row)", actions)

    def test_no_disable_without_flag(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._write(self.models, "test-model.md", CARD_MD)
        self._load()
        (self.providers / "test-provider.md").unlink()
        (self.models / "test-model.md").unlink()
        self._load()
        self.assertTrue(ApiProvider.objects.get(slug="test-provider").enabled)
        self.assertTrue(AiModel.objects.get(provider_model_id="test-model-free").enabled)

    def test_reappearing_file_reenables(self):
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._load(disable_missing=True)
        (self.providers / "test-provider.md").unlink()
        self._load(disable_missing=True)
        self.assertFalse(ApiProvider.objects.get(slug="test-provider").enabled)
        self._write(self.providers, "test-provider.md", PROVIDER_MD)
        self._load(disable_missing=True)
        self.assertTrue(ApiProvider.objects.get(slug="test-provider").enabled)
