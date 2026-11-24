"""Tests for deterministic free-offering extraction (part 1 only)."""

from __future__ import annotations

import json

from registry.catalog.build import build_dataset
from registry.catalog.cards import DOC_SOURCE, SOURCE as SOURCE_CARDS, load_api_bases
from registry.catalog.free import (
    all_zero_prices,
    build_free_dataset,
    free_markers,
    model_list_items,
    prepare_free_output,
)
from registry.catalog.sources import SourceBundle, model_list_url
from registry.catalog.write import CATALOG_UPDATED_AT, sync_free_candidates, sync_free_models


def test_free_marker_detection_is_boundary_aware():
    assert free_markers("deepseek-v4-flash-free") == ["-free"]
    assert free_markers("corethink:free", "Free Model") == [":free"]
    assert free_markers("openrouter/free", "x-ai/grok-code-fast-1:optimized:free") == ["/free", ":free"]
    assert free_markers("freellm-router") == []
    assert free_markers("not-freebie") == []


def test_zero_price_detection_handles_nested_cost_structures():
    assert all_zero_prices({"input": 0, "output": 0}) is True
    assert all_zero_prices({"text": {"input": {"price": 0}, "output": {"price": 0}}}) is True
    assert all_zero_prices({"input": 0, "output": 0.1}) is False
    assert all_zero_prices({}) is False


def test_provider_model_list_parsers():
    assert model_list_url("groq", "https://api.groq.com/openai/v1") == "https://api.groq.com/openai/v1/models"
    assert model_list_url("perplexity", "https://api.perplexity.ai") == "https://api.perplexity.ai/v1/models"
    assert model_list_url("google-gemini", "https://generativelanguage.googleapis.com") == (
        "https://generativelanguage.googleapis.com/v1beta/models"
    )
    assert model_list_url("local", "http://localhost:1234/v1") == ""
    assert model_list_url("vertex", "https://{region}-aiplatform.googleapis.com/v1") == ""

    openai_shape = {"object": "list", "data": [{"id": "model-a:free"}]}
    assert model_list_items(openai_shape) == [{"id": "model-a:free"}]
    assert model_list_items({"models": {"model-b": {"owned_by": "x"}}}) == [
        {"owned_by": "x", "id": "model-b"}
    ]
    assert model_list_items([{"id": "model-c"}]) == [{"id": "model-c"}]


def _bundle() -> SourceBundle:
    return SourceBundle(
        opencode_live={
            "data": [
                {
                    "id": "deepseek-v4.1-flash-free",
                    "object": "model",
                    "owned_by": "opencode",
                    "name": "DeepSeek V4.1 Flash Free",
                    "canonical_id": "deepseek/deepseek-v4.1-flash",
                    "capabilities": {
                        "tools": {"supported": True},
                        "reasoning": {"supported": True, "effort": ["low", "high"]},
                        "structured_output": True,
                        "temperature": True,
                    },
                    "limit": {"context": 200000, "output": 32000},
                    "cost": {"text": {"input": {"price": 0}, "output": {"price": 0}}},
                    "api": {"chat-completions": {"base_url": "https://opencode.ai/inference/openai/v1"}},
                    "release_date": "2026-10-17",
                },
                {"id": "paid-model", "cost": {"input": 3, "output": 15}},
            ]
        },
        opencode={
            "kilo": {
                "id": "kilo",
                "name": "Kilo Gateway",
                "models": {
                    "corethink:free": {
                        "id": "corethink:free",
                        "name": "CoreThink",
                        "cost": {"input": 0, "output": 0},
                        "release_date": "2026-01-01",
                    }
                },
            }
        },
        freellmapi={
            "version": "2026.11.23",
            "tier": "monthly",
            "platforms": [{"id": "newprov", "name": "New Provider"}],
            "models": [
                {
                    "platform": "newprov",
                    "modelId": "test-model",
                    "displayName": "Test Model",
                    "contextWindow": 131072,
                    "supportsTools": True,
                    "supportsVision": True,
                    "limits": {"rpm": 10, "rpd": 100, "tpm": None},
                    "monthlyTokenBudget": "free · 2/min per IP",
                    "intelligenceRank": 71,
                    "speedRank": 9,
                    "enabled": True,
                }
            ],
            "quirks": [
                {
                    "slug": "keyless",
                    "title": "Keyless",
                    "body": "No key required.",
                    "severity": "info",
                    "targets": [{"platform": "newprov", "modelGlob": None}],
                }
            ],
        },
        awesome={
            "providers": [
                {
                    "name": "Extra Free",
                    "baseUrl": "https://api.extra.example/v1",
                    "description": "Permanent free tier, no card.",
                    "models": [
                        {
                            "id": "extra-model",
                            "name": "Extra Model",
                            "context": "32K",
                            "rateLimit": "20 RPM, 1,000 RPD",
                        }
                    ],
                }
            ]
        },
        provider_models={
            "groq": {
                "_meta": {
                    "provider": "groq",
                    "url": "https://api.groq.com/openai/v1/models",
                    "status": "ok",
                },
                "data": {
                    "object": "list",
                    "data": [
                        {"id": "hidden-model:free", "owned_by": "groq"},
                        {"id": "regular-model"},
                    ],
                },
            }
        },
    )


def test_build_free_dataset_extracts_all_extractable_facts():
    providers = {
        "opencode-zen": {"name": "OpenCode Zen", "api_base": "https://opencode.ai/inference/openai/v1"},
        "kilo-code": {"name": "Kilo Gateway", "api_base": "https://api.kilo.ai/v1"},
        "newprov": {"name": "New Provider", "api_base": "https://api.newprov.example/v1"},
        "extra-free": {"name": "Extra Free", "api_base": "https://api.extra.example/v1"},
        "groq": {"name": "Groq", "api_base": "https://api.groq.com/openai/v1"},
    }
    dataset = build_free_dataset(_bundle(), providers)

    assert dataset["_generated_by"] == "registry.catalog"
    assert dataset["schema_version"] == 3
    assert dataset["counts"] == {"providers": 5, "candidates": 5}
    assert set(dataset["sources"]) == {
        "opencode-live-models",
        "opencode-models-api",
        "freellmapi-catalog",
        "awesome-free-llm-apis",
        "provider-models-api",
    }

    by_key = {(item["provider"], item["slug"]): item for item in dataset["candidates"]}
    assert set(by_key) == {
        ("opencode-zen", "deepseek-v4-1-flash"),
        ("kilo-code", "corethink"),
        ("newprov", "test-model"),
        ("extra-free", "extra-model"),
        ("groq", "hidden-model"),
    }

    live = by_key[("opencode-zen", "deepseek-v4-1-flash")]
    assert "free-marker:-free" in live["signals"]
    assert "zero-cost" in live["signals"]
    assert live["facts"]["reasoning_options"] == [{"type": "effort", "values": ["low", "high"]}]
    assert live["facts"]["context_window"] == 200000
    assert live["facts"]["api_bases"] == ["https://opencode.ai/inference/openai/v1"]
    assert live["provider_model_ids"] == ["deepseek-v4.1-flash-free"]

    catalog = by_key[("newprov", "test-model")]
    assert "freellmapi:monthly-catalog" in catalog["signals"]
    assert catalog["facts"]["catalog_intelligence_rank"] == 71
    assert catalog["facts"]["quota_label"] == "free · 2/min per IP"
    assert catalog["limits"] == {"rpm": 10, "rpd": 100, "rpm_ip": 2}
    assert "limits" not in catalog["facts"]
    assert catalog["raw"]["freellmapi-catalog"][0]["quirks_resolved"][0]["slug"] == "keyless"

    awesome = by_key[("extra-free", "extra-model")]
    assert "awesome:free-llm-provider" in awesome["signals"]
    assert awesome["facts"]["context_window"] == 32000
    assert awesome["limits"] == {"rpm": 20, "rpd": 1000}
    assert "awesome:free-tier-description" in dataset["providers"]["extra-free"]["signals"]

    hidden = by_key[("groq", "hidden-model")]
    assert "free-marker::free" in hidden["signals"]
    assert hidden["api_bases"] == ["https://api.groq.com/openai/v1/models"]

    for candidate in dataset["candidates"]:
        assert candidate["_generated_by"] == "registry.catalog"
        assert "free" not in candidate
        assert "conditions" not in candidate
        assert candidate["sources"]


def test_freellmapi_budget_and_null_limits_are_normalized():
    bundle = _bundle()
    bundle.freellmapi["models"][0]["monthlyTokenBudget"] = "~3M"
    bundle.freellmapi["models"][0]["limits"] = {"rpm": 10, "rpd": None, "tpm": 250000}
    prepared = prepare_free_output(build_free_dataset(bundle, {}))

    candidate = next(
        item for item in prepared["dataset"]["candidates"] if item["model"] == "test-model"
    )
    assert candidate["limits"] == {"tokens_per_month": 3_000_000, "rpm": 10, "tpm": 250000}
    assert "limits" not in prepared["models"][("newprov", "test-model")]


def test_prepare_free_output_moves_model_data_into_model_files():
    bundle = _bundle()
    providers, models = build_dataset(bundle)
    prepared = prepare_free_output(build_free_dataset(bundle, providers), providers, models)

    assert prepared["created"] == [
        "groq/hidden-model",
        "kilo-code/corethink",
        "newprov/test-model",
        "opencode-zen/deepseek-v4-1-flash",
    ]
    assert prepared["enriched"] == ["extra-free/extra-model"]

    for item in prepared["dataset"]["candidates"]:
        assert set(item) <= {
            "_generated_by",
            "provider",
            "model",
            "model_name",
            "provider_model_id",
            "limits",
        }
        assert item["provider_model_id"]
        assert item["model_name"]

    by_model = {item["model"]: item for item in prepared["dataset"]["candidates"]}
    assert by_model["test-model"]["provider_model_id"] == "test-model"
    assert by_model["test-model"]["limits"] == {"rpm": 10, "rpd": 100, "rpm_ip": 2}
    assert by_model["extra-model"]["provider_model_id"] == "extra-model"
    assert by_model["extra-model"]["limits"] == {"rpm": 20, "rpd": 1000}
    assert by_model["hidden-model"]["provider_model_id"] == "hidden-model:free"
    assert "limits" not in by_model["hidden-model"]

    assert "api_base" not in prepared["dataset"]["providers"]["newprov"]

    live = prepared["models"][("opencode-zen", "deepseek-v4-1-flash")]
    assert live["generated_from"] == "free-candidates"
    assert live["context_window"] == 200000
    assert live["reasoning_options"] == [{"type": "effort", "values": ["low", "high"]}]
    assert live["provider_model_ids"] == ["deepseek-v4.1-flash-free"]
    assert live["raw"]["opencode-live-models"]
    assert live["sources"]

    existing = prepared["models"][("extra-free", "extra-model")]
    assert "generated_from" not in existing
    assert "raw" not in existing
    assert existing["context_window"] == 32000  # base value survives
    assert existing["candidate_evidence"]["raw"]["awesome-free-llm-apis"]

    groq_provider = prepared["providers"]["groq"]
    assert groq_provider["generated_from"] == "free-candidates"
    assert groq_provider["api_base"] == "https://api.groq.com/openai/v1"


def test_prepare_free_output_resolves_candidate_onto_existing_model_by_raw_id():
    raw_id = "sourceful/riverflow-v2-fast-preview"
    base_model = {
        "_generated_by": "registry.catalog",
        "provider": "openrouter",
        "model": "riverflow",
        "provider_model_ids": [raw_id],
        "aliases": ["Riverflow V2 Fast Preview", raw_id, "riverflow-v2"],
        "sources": [{"source": "opencode-models-api", "provider": "openrouter", "raw_id": "riverflow"}],
    }
    candidate = {
        "_generated_by": "registry.catalog",
        "provider": "openrouter",
        "slug": "riverflow-v2",
        "provider_model_ids": [raw_id],
        "aliases": ["Riverflow V2 Fast Preview", raw_id],
        "facts": {},
        "raw": {"provider-models-api": [{"id": raw_id}]},
        "sources": [{"source": "provider-models-api", "provider": "openrouter", "raw_id": raw_id}],
        "signals": ["free-marker:-free"],
        "source_names": ["provider-models-api"],
    }
    dataset = {"candidates": [candidate], "providers": {}, "sources": [], "counts": {}}

    prepared = prepare_free_output(dataset, {}, {("openrouter", "riverflow"): base_model})

    assert prepared["created"] == []
    assert prepared["enriched"] == ["openrouter/riverflow"]
    assert set(prepared["models"]) == {("openrouter", "riverflow")}
    assert prepared["dataset"]["candidates"][0]["model"] == "riverflow"
    assert prepared["dataset"]["candidates"][0]["provider_model_id"] == raw_id
    assert prepared["models"][("openrouter", "riverflow")]["candidate_evidence"]["raw"]


def test_load_api_bases_reads_cards_and_documented_overrides(tmp_path):
    cards = tmp_path / "providers"
    cards.mkdir()
    (cards / "newprov.md").write_text(
        "---\nname: New Provider\napi_base: https://card.example/v1\n---\n",
        encoding="utf-8",
    )

    bases = load_api_bases(tmp_path)

    assert bases["newprov"]["api_base"] == "https://card.example/v1"
    assert bases["newprov"]["source"] == SOURCE_CARDS
    assert bases["router9"]["api_base"] == "https://api.router9.com/v1"
    assert bases["router9"]["source"] == DOC_SOURCE


def test_prepare_free_output_uses_api_base_for_missing_provider():
    bundle = _bundle()
    providers, models = build_dataset(bundle)
    dataset = build_free_dataset(bundle, providers)
    api_bases = {
        "newprov": {
            "api_base": "https://api.newprov.example/v1",
            "source": SOURCE_CARDS,
            "ref": {"source": SOURCE_CARDS, "provider": "newprov", "raw_id": "newprov.md"},
            "card": "newprov.md",
        }
    }

    prepared = prepare_free_output(dataset, providers, models, api_bases)

    provider = prepared["providers"]["newprov"]
    assert provider["api_base"] == "https://api.newprov.example/v1"
    assert provider["api_base_source"] == "curated-card"
    assert {"source": SOURCE_CARDS, "provider": "newprov", "raw_id": "newprov.md"} in provider["sources"]

    model = prepared["models"][("newprov", "test-model")]
    assert model["api_bases"] == ["https://api.newprov.example/v1"]

    candidate = next(item for item in prepared["dataset"]["candidates"] if item["provider"] == "newprov")
    assert candidate["model"] == "test-model"
    assert SOURCE_CARDS in prepared["dataset"]["sources"]


def test_sync_free_candidates_splits_by_provider_and_is_byte_stable(tmp_path):
    dataset = prepare_free_output(build_free_dataset(_bundle()))["dataset"]
    base = tmp_path / "candidates"
    legacy = base / "candidates.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"_generated_by": "registry.catalog"}\n', encoding="utf-8")

    summary = sync_free_candidates(dataset, base)

    assert summary["written"] == 6  # index + five providers
    assert summary["total_files"] == 6
    assert summary["removed"] == 1
    assert not legacy.exists()
    assert (base / "index.json").exists()
    assert (base / "groq.json").exists()

    index = json.loads((base / "index.json").read_text(encoding="utf-8"))
    assert [item["provider"] for item in index["providers"]] == [
        "extra-free",
        "groq",
        "kilo-code",
        "newprov",
        "opencode-zen",
    ]

    groq = json.loads((base / "groq.json").read_text(encoding="utf-8"))
    assert groq["provider"] == "groq"
    assert groq["candidate_count"] == 1
    assert groq["candidates"][0]["model"] == "hidden-model"
    assert groq["candidates"][0]["provider_model_id"] == "hidden-model:free"
    assert set(groq["candidates"][0]) == {"model", "model_name", "provider_model_id"}
    assert {item["model"] for item in groq["candidates"]} == {"hidden-model"}

    written = {path.name: path.read_text(encoding="utf-8") for path in sorted(base.glob("*.json"))}
    again = sync_free_candidates(dataset, base)
    assert again["written"] == 0
    assert again["unchanged"] == 6
    assert {path.name: path.read_text(encoding="utf-8") for path in sorted(base.glob("*.json"))} == written


def test_sync_free_candidates_never_overwrites_manual_file(tmp_path):
    base = tmp_path / "candidates"
    path = base / "manual.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"manual": true}\n', encoding="utf-8")

    sync_free_candidates(prepare_free_output(build_free_dataset(_bundle()))["dataset"], base)

    assert path.read_text(encoding="utf-8") == '{"manual": true}\n'


def test_sync_free_models_stamps_generated_files(tmp_path):
    bundle = _bundle()
    providers, models = build_dataset(bundle)
    prepared = prepare_free_output(build_free_dataset(bundle, providers), providers, models)
    first = "2026-11-24T00:00:00Z"
    second = "2026-11-25T00:00:00Z"
    model_file = tmp_path / "providers" / "newprov" / "test-model.json"

    sync_free_models(prepared["providers"], prepared["models"], tmp_path, updated_at=first)
    assert json.loads(model_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first

    again = sync_free_models(prepared["providers"], prepared["models"], tmp_path, updated_at=second)
    assert again["written"] == 0
    assert json.loads(model_file.read_text(encoding="utf-8"))[CATALOG_UPDATED_AT] == first


def test_sync_free_models_writes_and_prunes_only_free_generated_files(tmp_path):
    bundle = _bundle()
    providers, models = build_dataset(bundle)
    prepared = prepare_free_output(build_free_dataset(bundle, providers), providers, models)

    summary = sync_free_models(prepared["providers"], prepared["models"], tmp_path)
    assert summary["written"] == 9  # four free-only providers + five model files
    assert (tmp_path / "providers" / "opencode-zen" / "deepseek-v4-1-flash.json").exists()
    assert (tmp_path / "providers" / "groq" / "groq.json").exists()

    stale = tmp_path / "providers" / "stale" / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(
        '{"_generated_by": "registry.catalog", "generated_from": "free-candidates"}\n',
        encoding="utf-8",
    )
    normal = tmp_path / "providers" / "normal" / "normal.json"
    normal.parent.mkdir(parents=True)
    normal.write_text('{"_generated_by": "registry.catalog"}\n', encoding="utf-8")
    manual = tmp_path / "providers" / "manual" / "manual.json"
    manual.parent.mkdir(parents=True)
    manual.write_text('{"manual": true}\n', encoding="utf-8")

    again = sync_free_models(prepared["providers"], prepared["models"], tmp_path)
    assert again["removed"] == 1
    assert not stale.exists()
    assert normal.exists()
    assert manual.exists()
    assert again["written"] == 0
    assert again["unchanged"] == 9
