"""Tests for the provider-local catalog generator."""

from __future__ import annotations

import json

from registry.catalog.build import build_dataset
from registry.catalog.normalize import (
    GENERATED_BY,
    canonical_model_slug,
    parse_budget_limits,
    parse_rate_limit,
    parse_size,
    resolve_provider_slug,
)
from registry.catalog.sources import SourceBundle
from registry.catalog.versions import model_base, version_info
from registry.catalog.write import CATALOG_UPDATED_AT, sync_dataset


def test_canonical_model_slug_variants():
    cases = {
        "openai/gpt-oss-120b": "gpt-oss-120b",
        "deepseek-v4-flash:free": "deepseek-v4-flash",
        "GLM-5.3-Flash": "glm-5-3-flash",
        "glm_5_3_flash": "glm-5-3-flash",
        "gemini-3-flash-preview": "gemini-3-flash",
        "@cf/meta/llama-3.2-1b": "llama-3-2-1b",
        "us.anthropic.claude-sonnet-4-6": "claude-sonnet-4-6",
        "accounts/fireworks/models/qwen3-235b": "qwen3-235b",
        "beam-free-preview": "beam",
        "zai-org-glm-4.6": "glm-4-6",
        "zai-glm-4.7": "glm-4-7",
        "z-ai/glm-4.6": "glm-4-6",
        "moonshot-kimi-k2-instruct": "kimi-k2-instruct",
    }
    for raw, expected in cases.items():
        assert canonical_model_slug(raw) == expected


def test_provider_alias_resolution():
    assert resolve_provider_slug("huggingface", "Hugging Face") == "huggingface"
    assert resolve_provider_slug("Hugging Face", "Hugging Face") == "huggingface"
    assert resolve_provider_slug("opencode", "OpenCode Zen") == "opencode-zen"
    assert resolve_provider_slug("kilo", "Kilo Gateway") == "kilo-code"
    assert resolve_provider_slug("nvidia", "Nvidia") == "nvidia-nim"
    assert resolve_provider_slug("llmgateway", "LLM Gateway") == "llmgateway"
    assert resolve_provider_slug("llm7-io", "LLM7.io") == "llm7"
    assert resolve_provider_slug("ovhcloud", "OVHcloud") == "ovhcloud-ai-endpoints"
    assert resolve_provider_slug("new-provider", "New Provider") == "new-provider"


def test_parse_helpers():
    assert parse_size("131K") == 131000
    assert parse_size("1M") == 1_000_000
    assert parse_size(8192) == 8192
    assert parse_size("n/a") is None
    assert parse_rate_limit("30 RPM, 1,000 RPD") == {"rpm": 30, "rpd": 1000}
    assert parse_rate_limit("20 requests/minute") == {"rpm": 20}
    assert parse_rate_limit("200 req/hr") == {"rph": 200}
    assert parse_rate_limit("~1 RPS, 500K TPM") == {"rps": 1, "tpm": 500_000}
    assert parse_rate_limit("15 RPM, 20K TPD") == {"rpm": 15, "tpd": 20_000}
    assert parse_rate_limit("~1M tokens/month (shared)") == {"tokens_per_month": 1_000_000}
    assert parse_rate_limit("free · 2/min per IP") == {"rpm_ip": 2}
    assert parse_rate_limit("free · 20k tok/day") == {"tpd": 20_000}
    assert parse_rate_limit("2,000 RPD total; <=500 RPD/model") == {"rpd": 2000, "rpd_model": 500}
    assert parse_rate_limit("1 concurrent request") == {"concurrency": 1}
    assert parse_rate_limit("10K neurons/day") == {}
    assert parse_rate_limit("$0.25/week shared credit") == {}
    assert parse_budget_limits("5,000 requests/month; 100 requests and $0.50 usage/day shared") == {
        "requests_per_month": 5000
    }
    assert parse_budget_limits("~3M") == {"tokens_per_month": 3_000_000}
    assert parse_budget_limits("~10-20M") == {}


def test_version_info_and_model_base():
    assert model_base("devstral-small-2505", {"release_date": "2025-05-01"}) == "devstral-small"
    assert version_info("glm-4-32b-0414", {"release_date": "2025-04-14"}).date == "20250414"
    assert version_info("qwen3-235b-a22b-07-25", {"last_updated": "2025-07-21"}).date == "20250725"
    info = version_info("qwen3-235b-a22b-instruct-2507-tee", {})
    assert info.base == "qwen3-235b-a22b"
    assert info.date == "20250700"
    assert info.modifiers == ("instruct", "tee")
    assert model_base("qwen3-235b") == "qwen3-235b-a22b"
    # A context length is not a date.
    assert model_base("llama3-70b-8192", {"release_date": "2024-04-18"}) == "llama3-70b-8192"


def _opencode_bundle() -> SourceBundle:
    return SourceBundle(
        opencode={
            "groq": {
                "id": "groq",
                "name": "Groq",
                "api": "https://api.groq.com/openai/v1",
                "env": ["GROQ_API_KEY"],
                "models": {
                    "deepseek-v4-flash:free": {
                        "id": "deepseek-v4-flash:free",
                        "name": "DeepSeek V4 Flash",
                        "family": "deepseek-v4",
                        "reasoning": True,
                        "reasoning_options": [{"type": "effort", "values": ["high", "max"]}],
                        "tool_call": True,
                        "structured_output": True,
                        "temperature": True,
                        "interleaved": {"field": "reasoning_content"},
                        "release_date": "2026-06-13",
                        "last_updated": "2026-06-13",
                        "limit": {"context": 131072, "output": 32768},
                        "cost": {"input": 0, "output": 0},
                    }
                },
            }
        },
        freellmapi={
            "version": "2026.11.19",
            "platforms": [{"id": "groq", "name": "Groq"}],
            "models": [
                {
                    "platform": "groq",
                    "modelId": "deepseek-v4-flash:free",
                    "displayName": "DeepSeek V4 Flash (catalog)",
                    "contextWindow": 65536,
                    "limits": {"rpm": 30, "tpd": None},
                    "monthlyTokenBudget": "~6M",
                },
                {
                    "platform": "groq",
                    "modelId": "catalog-only-one",
                    "displayName": "Catalog Only One",
                    "contextWindow": 8192,
                    "monthlyTokenBudget": "~1M",
                },
            ],
            "quirks": [],
        },
        awesome={
            "providers": [
                {
                    "name": "Groq",
                    "baseUrl": "https://api.groq.com/openai/v1",
                    "url": "https://console.groq.com/keys",
                    "description": "Fast inference.",
                    "models": [
                        {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "context": "131K"},
                        {"id": "awesome-only-two", "name": "Awesome Only Two", "context": "32K"},
                    ],
                },
                {
                    "name": "Awesome Only Provider",
                    "baseUrl": "https://api.awesome-only.example/v1",
                    "models": [{"id": "awesome-provider-model", "name": "Awesome Provider Model"}],
                },
            ]
        },
    )


def test_opencode_is_base_and_catalogs_only_add_missing():
    providers, models = build_dataset(_opencode_bundle())

    assert set(providers) == {"groq", "awesome-only-provider"}
    assert providers["groq"]["api_base"] == "https://api.groq.com/openai/v1"
    assert providers["groq"]["model_count"] == 3
    assert providers["awesome-only-provider"]["api_base"] == "https://api.awesome-only.example/v1"
    assert providers["awesome-only-provider"]["model_count"] == 1
    assert set(models) == {
        ("groq", "deepseek-v4-flash"),
        ("groq", "catalog-only-one"),
        ("groq", "awesome-only-two"),
        ("awesome-only-provider", "awesome-provider-model"),
    }

    base = models[("groq", "deepseek-v4-flash")]
    assert base["release_date"] == "2026-06-13"
    assert base["reasoning_options"][0]["values"] == ["high", "max"]
    assert base["context_window"] == 131072
    assert base["cost"] == {"input": 0, "output": 0}
    assert "deepseek-v4-flash:free" in base["aliases"]
    assert {source["source"] for source in base["sources"]} == {"opencode-models-api"}

    catalog_only = models[("groq", "catalog-only-one")]
    assert catalog_only["quota_label"] == "~1M"
    assert {source["source"] for source in catalog_only["sources"]} == {"freellmapi-catalog"}

    awesome_only = models[("groq", "awesome-only-two")]
    assert awesome_only["context_window"] == 32000
    assert {source["source"] for source in awesome_only["sources"]} == {"awesome-free-llm-apis"}

    for record in (*providers.values(), *models.values()):
        assert record["_generated_by"] == GENERATED_BY
        assert "free" not in record
        assert "conditions" not in record


def test_variants_collapse_within_their_provider():
    models_payload = {
        "Qwen/Qwen3-235B-A22B": {
            "id": "Qwen/Qwen3-235B-A22B",
            "name": "Qwen3 235B A22B",
            "release_date": "2025-04-29",
        },
        "qwen3-235b-a22b-instruct-2507": {
            "id": "qwen3-235b-a22b-instruct-2507",
            "name": "Qwen3 235B A22B Instruct 2507",
            "release_date": "2025-07-30",
        },
        "qwen3-235b-a22b-thinking-2507": {
            "id": "qwen3-235b-a22b-thinking-2507",
            "name": "Qwen3 235B A22B Thinking 2507",
            "release_date": "2025-07-30",
        },
        "qwen3-235b-a22b-fp8": {"id": "qwen3-235b-a22b-fp8", "name": "Qwen3 235B A22B FP8"},
        "qwen3-235b-a22b-07-25": {
            "id": "qwen3-235b-a22b-07-25",
            "name": "Qwen3 235B A22B Instruct 2507",
            "last_updated": "2025-07-21",
        },
        "qwen3-235b": {"id": "qwen3-235b", "name": "Qwen3 235B", "release_date": "2025-08-06"},
        "devstral-small-2505": {
            "id": "devstral-small-2505",
            "name": "Devstral Small 2505",
            "release_date": "2025-05-01",
        },
        "devstral-small-2512": {
            "id": "devstral-small-2512",
            "name": "Devstral Small 2 2512",
            "release_date": "2025-12-09",
        },
    }
    bundle = SourceBundle(
        opencode={
            "groq": {
                "id": "groq",
                "name": "Groq",
                "api": "https://api.groq.com/openai/v1",
                "models": models_payload,
            }
        }
    )

    _, models = build_dataset(bundle)

    assert set(models) == {("groq", "qwen3-235b-a22b"), ("groq", "devstral-small")}
    qwen = models[("groq", "qwen3-235b-a22b")]
    assert qwen["canonical_id"] == "Qwen/Qwen3-235B-A22B"
    assert set(qwen["variants"]) == {
        "qwen3-235b-a22b-instruct-2507",
        "qwen3-235b-a22b-thinking-2507",
        "qwen3-235b-a22b-fp8",
        "qwen3-235b-a22b-07-25",
        "qwen3-235b",
    }
    assert set(qwen["provider_model_ids"]) == {
        key for key in models_payload if key.startswith("qwen3-235b") or key.startswith("Qwen/")
    }

    devstral = models[("groq", "devstral-small")]
    assert devstral["name"] == "Devstral Small 2 2512"
    assert set(devstral["variants"]) == {"devstral-small-2505", "devstral-small-2512"}


def test_providers_without_a_usable_api_are_dropped():
    bundle = SourceBundle(
        opencode={
            "usable": {
                "id": "usable",
                "name": "Usable",
                "api": "https://api.usable.example/v1",
                "models": {"model-a": {"id": "model-a", "name": "Model A"}},
            },
            "vertex": {
                "id": "vertex",
                "name": "Vertex",
                "models": {
                    "model-b": {
                        "id": "model-b",
                        "name": "Model B",
                        "provider": {"api": "https://vertex.example/v1"},
                    }
                },
            },
            "anthropic": {
                "id": "anthropic",
                "name": "Anthropic",
                "npm": "@ai-sdk/anthropic",
                "models": {"claude-test": {"id": "claude-test", "name": "Claude Test"}},
            },
            "unknown-sdk": {
                "id": "unknown-sdk",
                "name": "Unknown SDK",
                "npm": "@example/unknown-provider",
                "models": {"model-unknown": {"id": "model-unknown", "name": "Model Unknown"}},
            },
            "dropme": {
                "id": "dropme",
                "name": "Drop Me",
                "models": {"model-c": {"id": "model-c", "name": "Model C"}},
            },
            "mixed": {
                "id": "mixed",
                "name": "Mixed",
                "models": {
                    "model-d": {"id": "model-d", "provider": {"api": "https://one.example/v1"}},
                    "model-e": {"id": "model-e", "provider": {"api": "https://two.example/v1"}},
                },
            },
        }
    )

    providers, models = build_dataset(bundle)

    assert set(providers) == {"usable", "vertex", "anthropic"}
    assert providers["usable"]["api_base"] == "https://api.usable.example/v1"
    assert providers["vertex"]["api_base"] == "https://vertex.example/v1"
    assert providers["anthropic"]["api_base"] == "https://api.anthropic.com/v1"
    assert providers["anthropic"]["api_base_source"] == "sdk-default"
    assert set(models) == {("usable", "model-a"), ("vertex", "model-b"), ("anthropic", "claude-test")}


def test_models_older_than_2025_are_dropped():
    bundle = SourceBundle(
        opencode={
            "fresh": {
                "id": "fresh",
                "name": "Fresh",
                "api": "https://api.fresh.example/v1",
                "models": {
                    "old-one": {
                        "id": "old-one",
                        "release_date": "2024-01-01",
                        "last_updated": "2024-12-31",
                    },
                    "refreshed-two": {
                        "id": "refreshed-two",
                        "release_date": "2024-05-01",
                        "last_updated": "2025-01-01",
                    },
                    "undated-three": {"id": "undated-three"},
                    "new-four": {"id": "new-four", "release_date": "2025-03-01"},
                },
            },
            "only-old": {
                "id": "only-old",
                "name": "Only Old",
                "api": "https://api.old.example/v1",
                "models": {"ancient-five": {"id": "ancient-five", "release_date": "2023-08-01"}},
            },
        }
    )

    providers, models = build_dataset(bundle)

    assert set(providers) == {"fresh"}
    assert set(models) == {
        ("fresh", "refreshed-two"),
        ("fresh", "undated-three"),
        ("fresh", "new-four"),
    }


def test_sync_dataset_writes_local_files_and_prunes_legacy_models(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    (tmp_path / "providers" / "groq").mkdir(parents=True)
    (tmp_path / "models").mkdir()

    stale = tmp_path / "providers" / "gone" / "gone.json"
    stale.parent.mkdir()
    stale.write_text(json.dumps({"_generated_by": GENERATED_BY}), encoding="utf-8")
    legacy = tmp_path / "models" / "legacy.json"
    legacy.write_text(json.dumps({"_generated_by": GENERATED_BY}), encoding="utf-8")
    manual_json = tmp_path / "models" / "manual.json"
    manual_json.write_text('{"slug": "manual"}', encoding="utf-8")
    manual_md = tmp_path / "models" / "manual.md"
    manual_md.write_text("---\nslug: manual\n---\n", encoding="utf-8")
    card = tmp_path / "providers" / "groq" / "groq.md"
    card.write_text("---\nname: Groq\n---\n", encoding="utf-8")

    summary = sync_dataset(providers, models, tmp_path)
    assert summary["written"] == 6
    assert summary["removed"] == 2
    assert not stale.exists()
    assert not legacy.exists()
    assert manual_json.exists()
    assert manual_md.exists()
    assert card.exists()
    assert (tmp_path / "providers" / "groq" / "deepseek-v4-flash.json").exists()

    again = sync_dataset(providers, models, tmp_path)
    assert again["written"] == 0
    assert again["unchanged"] == 6


def test_sync_dataset_stamps_only_changed_records(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    first = "2026-11-24T00:00:00Z"
    second = "2026-11-25T00:00:00Z"
    provider_file = tmp_path / "providers" / "groq" / "groq.json"
    model_file = tmp_path / "providers" / "groq" / "deepseek-v4-flash.json"

    sync_dataset(providers, models, tmp_path, updated_at=first)
    assert json.loads(provider_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first
    assert json.loads(model_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first

    again = sync_dataset(providers, models, tmp_path, updated_at=second)
    assert again["written"] == 0
    assert json.loads(model_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first

    models[("groq", "deepseek-v4-flash")]["context_window"] = 12345
    changed = sync_dataset(providers, models, tmp_path, updated_at=second)
    assert changed["written"] == 1
    assert json.loads(model_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == second
    assert json.loads(provider_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first


def test_sync_dataset_preserves_free_generated_files(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    free_model = tmp_path / "providers" / "free-only" / "free-only.json"
    free_model.parent.mkdir(parents=True)
    free_model.write_text(
        json.dumps(
            {
                "_generated_by": GENERATED_BY,
                "generated_from": "free-candidates",
            }
        ),
        encoding="utf-8",
    )

    summary = sync_dataset(providers, models, tmp_path)

    assert free_model.exists()
    assert summary["removed"] == 0


def test_sync_dataset_preserves_candidate_evidence(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    evidence = {"raw": {"provider-models-api": [{"id": "probe"}]}}
    path = tmp_path / "providers" / "groq" / "deepseek-v4-flash.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"_generated_by": GENERATED_BY, "candidate_evidence": evidence}),
        encoding="utf-8",
    )

    sync_dataset(providers, models, tmp_path)

    assert json.loads(path.read_text(encoding="utf-8"))["candidate_evidence"] == evidence


def test_sync_dataset_preserves_curated_provider_fields(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    curated = {
        "description": "Curated description.",
        "setup_instructions": "1. Sign up.\n2. Create a key.",
        "url": "https://console.example.com",
        "api_key_url": "https://console.example.com/keys",
        "default_api_key": "public",
        "doc": "https://docs.example.com",
        "litellm_prefix": "example",
        "wire": {"transports": ["chat_completions"], "wire_verified": "2026-11-24"},
        "research_sources": ["https://docs.example.com", "https://console.example.com/pricing"],
    }
    path = tmp_path / "providers" / "groq" / "groq.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"_generated_by": GENERATED_BY, **curated}),
        encoding="utf-8",
    )

    sync_dataset(providers, models, tmp_path)
    first = json.loads(path.read_text(encoding="utf-8"))
    assert all(first[key] == value for key, value in curated.items())

    again = sync_dataset(providers, models, tmp_path)
    assert again["written"] == 0
    assert json.loads(path.read_text(encoding="utf-8")) == first


def test_sync_dataset_dry_run_changes_nothing(tmp_path):
    providers, models = build_dataset(_opencode_bundle())
    summary = sync_dataset(providers, models, tmp_path, dry_run=True)
    assert summary["written"] == 6
    assert summary["dry_run"] is True
    assert not (tmp_path / "providers" / "groq" / "deepseek-v4-flash.json").exists()
