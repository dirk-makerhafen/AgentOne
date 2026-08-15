from pathlib import Path

from django.test import TestCase

from registry.loader.load_providers import (
    _rate_limit_defaults,
    load_providers_manifest,
)
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


class RateLimitDefaultsTest(TestCase):
    """Tests for ``_rate_limit_defaults`` key mapping."""

    def test_request_rate_key_mapping(self):
        result = _rate_limit_defaults({"RPM": 40, "RPD": 200})
        self.assertEqual(result["limit_request_per_minute"], 40)
        self.assertEqual(result["limit_request_per_day"], 200)

    def test_token_rate_key_mapping(self):
        result = _rate_limit_defaults({"TPM": 5000, "TPD": 100000})
        self.assertEqual(result["limit_tokens_per_minute"], 5000)
        self.assertEqual(result["limit_tokens_per_day"], 100000)

    def test_hourly_keys_map_to_hourly_fields(self):
        result = _rate_limit_defaults({"RPH": 200, "TPH": 50000})
        self.assertEqual(result["limit_request_per_hour"], 200)
        self.assertEqual(result["limit_tokens_per_hour"], 50000)

    def test_per_second_converted_to_supported_minute_window(self):
        result = _rate_limit_defaults({"RPS": 1, "TPS": 50})
        self.assertEqual(result["limit_request_per_minute"], 60)
        self.assertEqual(result["limit_tokens_per_minute"], 3000)

    def test_parallel_calls_map(self):
        result = _rate_limit_defaults({"parallel_calls": 1})
        self.assertEqual(result["limit_parallel_calls"], 1)

    def test_consistent_key_overlap_keeps_most_conservative(self):
        result = _rate_limit_defaults({"RPS": 10, "RPM": 5})
        self.assertEqual(result["limit_request_per_minute"], 5)

    def test_ignores_zero_absent_and_non_numeric(self):
        result = _rate_limit_defaults({"RPM": 0, "RPD": None, "TPM": "abc"})
        self.assertEqual(result, {})


class LoadProvidersManifestRateLimitsTest(TestCase):
    """Provider-level free_info rate limits flow into provider + models."""

    def test_free_info_rate_limits_applied_to_provider_only(self):
        manifest = Path("/tmp/opencode-test-providers.yaml")
        manifest.write_text(
            """
providers:
  - name: Snowflake Test
    url: https://example.com/v1
    free_info:
      RPM: 15
      RPD: 1500
      TPD: 20000
""",
            encoding="utf-8",
        )
        try:
            details = []
            count = load_providers_manifest(manifest, details)
            self.assertEqual(count, 1)
            provider = ApiProvider.objects.get(name="Snowflake Test")
            self.assertEqual(provider.data["RPM"], 15)
            self.assertEqual(provider.data["RPD"], 1500)
            self.assertEqual(provider.limit_request_per_minute, 15)
            self.assertEqual(provider.limit_request_per_day, 1500)
            self.assertEqual(provider.limit_tokens_per_day, 20000)

            # Provider caps are not inherited into models — a model only gets a
            # limit from an explicit per-model key.
            model = AiModel.objects.create(
                api_provider=provider,
                name="test-model",
            )
            details = []
            load_providers_manifest(manifest, details)
            model.refresh_from_db()
            self.assertEqual(model.limit_request_per_minute, 0)
            self.assertEqual(model.limit_request_per_day, 0)
            self.assertEqual(model.limit_tokens_per_day, 0)
        finally:
            manifest.unlink(missing_ok=True)

    def test_free_info_hourly_limits_applied_to_provider(self):
        manifest = Path("/tmp/opencode-test-providers-hourly.yaml")
        manifest.write_text(
            """
providers:
  - name: Hourly Test
    url: https://example.com/v1
    free_info:
      RPH: 200
      TPH: 50000
""",
            encoding="utf-8",
        )
        try:
            details = []
            load_providers_manifest(manifest, details)
            provider = ApiProvider.objects.get(name="Hourly Test")
            self.assertEqual(provider.limit_request_per_hour, 200)
            self.assertEqual(provider.limit_tokens_per_hour, 50000)
            self.assertEqual(provider.limit_request_per_minute, 0)
        finally:
            manifest.unlink(missing_ok=True)

    def test_model_explicit_limit_overrides_provider(self):
        manifest = Path("/tmp/opencode-test-providers-2.yaml")
        manifest.write_text(
            """
providers:
  - name: Override Test
    url: https://example.com/v1
    free_info:
      RPM: 15
    models:
      - name: strict-model
        RPM: 3
      - name: relaxed-model
""",
            encoding="utf-8",
        )
        try:
            details = []
            load_providers_manifest(manifest, details)
            provider = ApiProvider.objects.get(name="Override Test")
            strict = AiModel.objects.get(api_provider=provider, name="strict-model")
            relaxed = AiModel.objects.get(api_provider=provider, name="relaxed-model")
            self.assertEqual(provider.limit_request_per_minute, 15)
            self.assertEqual(strict.limit_request_per_minute, 3)
            # No explicit key → model stays unlimited; the provider RPM 15 is a
            # provider-wide cap and is not inherited.
            self.assertEqual(relaxed.limit_request_per_minute, 0)
        finally:
            manifest.unlink(missing_ok=True)


class FreeModelsLoadingTest(TestCase):
    """Curated ``free_info.free_models`` entries merge a models.yaml catalog
    into per-provider ``AiModel`` records."""

    def setUp(self):
        self.catalog = Path("/tmp/models.yaml")
        self.catalog.write_text(
            """
models:
  - name: Deep V4
    family: vendor
    context_length: 1000000
    supports_reasoning: true
    supports_tool_call: true
    vision: true
    audio: true
    video: true
    total_parameters: 550
    active_parameters: 55
    description: "Canonical catalog description"
  - name: Small Model
    family: small
    context_length: 262000
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.catalog.unlink(missing_ok=True)
        Path("/tmp/opencode-test-free-models.yaml").unlink(missing_ok=True)
        Path("/tmp/opencode-test-free-models-2.yaml").unlink(missing_ok=True)

    def _write_manifest(self, path: str, body: str) -> Path:
        manifest = Path(path)
        manifest.write_text(body, encoding="utf-8")
        return manifest

    def test_free_models_merge_catalog_metadata_with_provider_id(self):
        manifest = self._write_manifest(
            "/tmp/opencode-test-free-models.yaml",
            """
providers:
  - name: Curated Test
    url: https://example.com/v1
    free_info:
      RPM: 10
      free_models:
        - model: Deep V4
          id: vendor/deep-v4-123
        - model: Small Model
          id: vendor/small
""",
        )
        details = []
        load_providers_manifest(manifest, details)
        provider = ApiProvider.objects.get(name="Curated Test")
        big = AiModel.objects.get(api_provider=provider, provider_model_id="vendor/deep-v4-123")
        small = AiModel.objects.get(api_provider=provider, provider_model_id="vendor/small")
        self.assertEqual(big.name, "Deep V4")
        self.assertEqual(big.provider_model_id, "vendor/deep-v4-123")
        self.assertEqual(big.family, "vendor")
        self.assertEqual(big.description, "Canonical catalog description")
        self.assertEqual(big.context_length, 1000000)
        self.assertTrue(big.supports_reasoning)
        self.assertTrue(big.supports_tool_call)
        self.assertTrue(big.vision)
        self.assertTrue(big.audio)
        self.assertTrue(big.video)
        self.assertEqual(big.total_parameters, 550)
        self.assertEqual(big.active_parameters, 55)
        # Provider RPM 10 is provider-wide; no per-model key → model unlimited.
        self.assertEqual(big.limit_request_per_minute, 0)
        self.assertEqual(provider.limit_request_per_minute, 10)
        self.assertEqual(small.context_length, 262000)
        self.assertFalse(small.supports_reasoning)

    def test_free_models_per_provider_overrides_catalog(self):
        manifest = self._write_manifest(
            "/tmp/opencode-test-free-models-2.yaml",
            """
providers:
  - name: Short Context
    url: https://example.com/v1
    free_info:
      free_models:
        - model: Deep V4
          id: short/deep-v4
          context_length: 262000
          RPM: 3
""",
        )
        details = []
        load_providers_manifest(manifest, details)
        provider = ApiProvider.objects.get(name="Short Context")
        model = AiModel.objects.get(api_provider=provider, provider_model_id="short/deep-v4")
        self.assertEqual(model.context_length, 262000)
        self.assertEqual(model.limit_request_per_minute, 3)

    def test_unknown_catalog_model_is_skipped(self):
        manifest = self._write_manifest(
            "/tmp/opencode-test-free-models-unknown.yaml",
            """
providers:
  - name: Broken Ref
    url: https://example.com/v1
    free_info:
      free_models:
        - model: Does Not Exist
          id: nope/nothing
""",
        )
        try:
            details = []
            count = load_providers_manifest(manifest, details)
            self.assertEqual(count, 1)
            provider = ApiProvider.objects.get(name="Broken Ref")
            self.assertEqual(provider.aimodels.count(), 0)
            skipped = [d for d in details if d["action"] == "skipped"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["name"], "Broken Ref/Does Not Exist")
        finally:
            manifest.unlink(missing_ok=True)
