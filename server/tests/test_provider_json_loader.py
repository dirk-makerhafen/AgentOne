"""Tests for the generated-JSON provider/model catalog loader.

Covers ``load_providers_json``: provider upsert, exact and ``~N`` ranks,
capability/context mapping, free-tier verdicts, multiple API model ids and
disable-missing semantics.
"""
import json
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase

from registry.loader.load_providers_json import load_providers_json
from server.models.providers.ai_model import AiModel as RawModel
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_provider import ApiProvider


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _provider(slug: str, **extra) -> dict:
    return {
        "_generated_by": "registry.catalog",
        "api_base": "https://api.example.com/v1",
        "name": "Example Provider",
        "slug": slug,
        **extra,
    }


def _model(provider: str, slug: str, **extra) -> dict:
    return {
        "_generated_by": "registry.catalog",
        "context_window": 131072,
        "max_output_tokens": 8192,
        "model": slug,
        "name": slug,
        "provider": provider,
        "provider_model_ids": [slug],
        **extra,
    }


class ProviderJsonLoaderTest(TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.providers = self._tmp / "providers"
        self.free = self._tmp / "free"
        self.providers.mkdir()
        self.free.mkdir()

    def _load(self, **kwargs):
        details = []
        count = load_providers_json(self.providers, self.free, details, **kwargs)
        return count, details

    def test_provider_and_model_upsert_with_exact_rank(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(
            self.providers / "example" / "test-model.json",
            _model(
                "example", "test-model",
                developer="TestDev", canonical_id="testdev/test-model", family="test",
                leaderboard_id="test-model", leaderboard_rank=42,
                reasoning=True, tool_call=True,
                modalities={"input": ["text", "image"], "output": ["text"]},
            ),
        )
        count, _ = self._load()
        self.assertEqual(count, 1)
        provider = ApiProvider.objects.get(slug="example")
        self.assertEqual(provider.url, "https://api.example.com/v1")
        raw = RawModel.objects.get(slug="test-model")
        self.assertEqual(raw.name, "test-model")
        self.assertEqual(raw.developer, "TestDev")
        self.assertEqual(raw.canonical_id, "testdev/test-model")
        self.assertEqual(raw.leaderboard_id, "test-model")
        self.assertEqual(raw.leaderboard_rank, 42)
        self.assertFalse(raw.leaderboard_rank_is_estimate)
        self.assertTrue(raw.supports_reasoning)
        self.assertTrue(raw.supports_tool_call)
        self.assertTrue(raw.vision)
        self.assertEqual(raw.context_length, 131072)
        offering = AiModelOffering.objects.get(api_provider=provider, provider_model_id="test-model")
        self.assertEqual(offering.model, raw)
        self.assertEqual(offering.leaderboard_rank, 42)
        self.assertTrue(offering.enabled)

    def test_estimated_rank_becomes_int_plus_flag(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(
            self.providers / "example" / "test-model.json",
            _model("example", "test-model", leaderboard_rank_estimated="~120"),
        )
        self._load()
        raw = RawModel.objects.get(slug="test-model")
        self.assertEqual(raw.leaderboard_rank, 120)
        self.assertTrue(raw.leaderboard_rank_is_estimate)
        offering = AiModelOffering.objects.get(provider_model_id="test-model")
        self.assertTrue(offering.leaderboard_rank_is_estimate)

    def test_free_verdict_sets_conditions_and_limits(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(
            self.providers / "example" / "test-model.json",
            _model("example", "test-model"),
        )
        _write_json(
            self.free / "example.json",
            {
                "generated_from": "free-reviews",
                "provider": "example",
                "candidates": [{
                    "model": "test-model",
                    "provider_model_id": "test-model",
                    "verdict": "free",
                    "verified": "2026-11-24",
                    "conditions": "Free with signup",
                    "limits": {"rpm": 20, "tpd": 1000},
                }],
            },
        )
        self._load()
        offering = AiModelOffering.objects.get(provider_model_id="test-model")
        self.assertTrue(offering.is_free)
        self.assertEqual(offering.conditions, "Free with signup")
        self.assertEqual(offering.free_verified, "2026-11-24")
        self.assertEqual(offering.limit_request_per_minute, 20)
        self.assertEqual(offering.limit_tokens_per_day, 1000)

    def test_rejected_verdict_is_not_free(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(self.providers / "example" / "test-model.json", _model("example", "test-model"))
        _write_json(
            self.free / "example.json",
            {
                "generated_from": "free-reviews",
                "provider": "example",
                "candidates": [{
                    "model": "test-model",
                    "provider_model_id": "test-model",
                    "verdict": "rejected",
                    "conditions": "Paid only",
                }],
            },
        )
        self._load()
        offering = AiModelOffering.objects.get(provider_model_id="test-model")
        self.assertFalse(offering.is_free)

    def test_multiple_provider_model_ids_create_multiple_offerings(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(
            self.providers / "example" / "test-model.json",
            _model("example", "test-model", provider_model_ids=["alias-1", "alias-2"]),
        )
        self._load()
        self.assertEqual(AiModelOffering.objects.count(), 2)
        self.assertEqual(RawModel.objects.count(), 1)

    def test_provider_without_api_base_keeps_existing_url(self):
        provider = ApiProvider.objects.create(
            slug="example", name="Example", url="https://curated.example.com/v1"
        )
        record = _provider("example")
        record.pop("api_base")
        _write_json(self.providers / "example" / "example.json", record)
        self._load()
        provider.refresh_from_db()
        self.assertEqual(provider.url, "https://curated.example.com/v1")

    def test_disable_missing_disables_absent_rows(self):
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        _write_json(self.providers / "example" / "test-model.json", _model("example", "test-model"))
        self._load()
        stale_provider = ApiProvider.objects.create(slug="stale", name="Stale", url="https://stale.example/v1")
        stale_offering = AiModelOffering.objects.create(
            api_provider=stale_provider,
            model=RawModel.objects.get(slug="test-model"),
            provider_model_id="stale-model",
        )
        self._load(disable_missing=True)
        stale_provider.refresh_from_db()
        stale_offering.refresh_from_db()
        self.assertFalse(stale_provider.enabled)
        self.assertFalse(stale_offering.enabled)
        self.assertTrue(AiModelOffering.objects.get(provider_model_id="test-model").enabled)

    def test_user_managed_provider_fields_preserved(self):
        provider = ApiProvider.objects.create(slug="example", name="Mine", url="https://mine.example/v1")
        # An ApiKey row marks the provider as user-managed.
        from server.models.providers.api_key import ApiKey
        ApiKey.objects.create(api_provider=provider, comment="my key", key="secret")
        _write_json(self.providers / "example" / "example.json", _provider("example"))
        self._load()
        provider.refresh_from_db()
        self.assertEqual(provider.name, "Mine")
        self.assertEqual(provider.url, "https://mine.example/v1")
