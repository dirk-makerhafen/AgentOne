"""Tests for the deterministic free-review merge (no DB, no generated writes)."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from registry.catalog.reviews import (
    MERGED_SOURCE,
    collect_reviews,
    sync_merged,
)

TODAY = date.today().isoformat()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_document(candidates: list[dict], provider: str = "groq") -> dict:
    return {
        "_generated_by": "registry.catalog",
        "schema_version": 3,
        "sources": ["opencode-models-api"],
        "provider": provider,
        "name": "Groq",
        "signals": [],
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _candidate(model: str, provider_model_id: str, limits: dict | None = None) -> dict:
    payload = {
        "model": model,
        "model_name": model.upper(),
        "provider_model_id": provider_model_id,
    }
    if limits:
        payload["limits"] = limits
    return payload


def _review(provider: str = "groq", models: dict | None = None) -> dict:
    return {
        "schema_version": 1,
        "provider": provider,
        "name": "Groq",
        "reviewed_at": TODAY,
        "sources": [
            {
                "id": "rate-limits",
                "url": "https://console.groq.com/docs/rate-limits",
                "title": "Rate limits",
                "accessed": TODAY,
            }
        ],
        "api_base": {
            "value": "https://api.groq.com/openai/v1",
            "status": "verified",
            "verified": TODAY,
            "source_ids": ["rate-limits"],
        },
        "limits": {"rpm": 30},
        "models": models or {},
    }


def _free_entry(model_id: str = "openai/gpt-oss-120b", **extra: object) -> dict:
    entry = {
        "verdict": "free",
        "provider_model_id": model_id,
        "conditions": "Free plan; account + API key",
        "verified": TODAY,
        "source_ids": ["rate-limits"],
    }
    entry.update(extra)
    return entry


def _setup(root: Path, base: dict, review: dict | None) -> None:
    _write(root / "candidates" / f"{base['provider']}.json", base)
    if review is not None:
        _write(root / "reviews" / f"{review['provider']}.json", review)


def test_collect_reviews_merges_verdicts_and_limits(tmp_path):
    base = _base_document(
        [
            _candidate("gpt-oss-120b", "openai/gpt-oss-120b", {"rpd": 1000}),
            _candidate("kimi-k2", "kimi-k2"),
        ]
    )
    review = _review(
        models={
            "gpt-oss-120b": _free_entry(limits={"tpm": 8000}),
        }
    )
    _setup(tmp_path, base, review)

    result = collect_reviews(tmp_path)

    assert not result.errors
    document = result.documents["groq.json"]
    by_model = {item["model"]: item for item in document["candidates"]}
    assert by_model["gpt-oss-120b"]["verdict"] == "free"
    assert by_model["gpt-oss-120b"]["conditions"] == "Free plan; account + API key"
    assert by_model["gpt-oss-120b"]["limits"] == {"rpd": 1000, "tpm": 8000}
    assert "verdict" not in by_model["kimi-k2"]
    assert document["limits"] == {"rpm": 30}
    assert document["review_sources"][0]["id"] == "rate-limits"
    assert document["reviewed_count"] == 1
    assert result.counts["candidates"] == 2
    assert result.counts["reviewed"] == 1
    assert result.counts["unreviewed"] == 1
    assert result.counts["free"] == 1
    assert any(issue.code == "unreviewed-candidate" for issue in result.warnings)


def test_collect_reviews_reports_unknown_ids_and_invalid_limits(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(
        models={
            "gpt-oss-120b": _free_entry(
                source_ids=["missing-source"],
                limits={"rpm": 30, "requests": 10, "cost_usd": 5},
            ),
            "not-generated": _free_entry("not/generated"),
        }
    )
    _setup(tmp_path, base, review)

    result = collect_reviews(tmp_path)
    codes = {issue.code for issue in result.errors}

    assert "unknown-source-id" in codes
    assert "invalid-limit" in codes
    assert "unknown-model" in codes
    # Only canonical numeric limits survive into a merged document.
    candidate = result.documents["groq.json"]["candidates"][0]
    assert candidate["limits"] == {"rpm": 30}


def test_collect_reviews_requires_gate_and_exact_provider_model_id(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(
        models={
            "gpt-oss-120b": {
                "verdict": "payment_gated",
                "provider_model_id": "wrong/id",
                "conditions": "Paid plan required",
                "verified": TODAY,
                "source_ids": ["rate-limits"],
            }
        }
    )
    _setup(tmp_path, base, review)

    result = collect_reviews(tmp_path)
    codes = {issue.code for issue in result.errors}

    assert "provider-model-id-mismatch" in codes
    assert "missing-gate" in codes


def test_collect_reviews_reports_missing_reviews_directory(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    _write(tmp_path / "candidates" / "groq.json", base)

    result = collect_reviews(tmp_path)

    assert any(issue.code == "missing-reviews-dir" for issue in result.errors)


def test_collect_reviews_rejects_review_for_unknown_provider(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    _setup(tmp_path, base, _review(provider="other", models={}))

    result = collect_reviews(tmp_path)

    assert any(issue.code == "unknown-provider" for issue in result.errors)


def test_sync_merged_is_idempotent_and_prunes_only_merged_files(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(models={"gpt-oss-120b": _free_entry()})
    _setup(tmp_path, base, review)
    result = collect_reviews(tmp_path)
    output = tmp_path / "free"

    first = sync_merged(result.documents, result.index, output)
    assert first["written"] == 2
    assert first["unchanged"] == 0

    second = sync_merged(result.documents, result.index, output)
    assert second["written"] == 0
    assert second["unchanged"] == 2

    stale = output / "stale.json"
    _write(stale, {"_generated_by": "registry.catalog", "generated_from": MERGED_SOURCE})
    manual = output / "manual.json"
    _write(manual, {"provider": "manual"})

    third = sync_merged(result.documents, result.index, output)
    assert third["removed"] == 1
    assert not stale.exists()
    assert manual.exists()


def test_sync_merged_refuses_to_overwrite_non_merged_file(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(models={"gpt-oss-120b": _free_entry()})
    _setup(tmp_path, base, review)
    result = collect_reviews(tmp_path)
    output = tmp_path / "free"
    output.mkdir()
    (output / "groq.json").write_text('{"provider": "hand-written"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to overwrite"):
        sync_merged(result.documents, result.index, output)


def test_merge_free_reviews_command_writes_merged_dataset(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(models={"gpt-oss-120b": _free_entry()})
    _setup(tmp_path, base, review)
    output = tmp_path / "free"

    stdout = StringIO()
    call_command(
        "merge_free_reviews",
        root=tmp_path,
        candidates_dir=tmp_path / "candidates",
        reviews_dir=tmp_path / "reviews",
        output_dir=output,
        stdout=stdout,
    )

    assert (output / "groq.json").exists()
    assert (output / "index.json").exists()
    assert "free: 1" in stdout.getvalue()


def test_merge_free_reviews_command_defaults_to_root_free(tmp_path):
    base = _base_document([_candidate("gpt-oss-120b", "openai/gpt-oss-120b")])
    review = _review(models={"gpt-oss-120b": _free_entry()})
    _setup(tmp_path, base, review)

    stdout = StringIO()
    call_command(
        "merge_free_reviews",
        root=tmp_path,
        candidates_dir=tmp_path / "candidates",
        reviews_dir=tmp_path / "reviews",
        stdout=stdout,
    )

    assert (tmp_path / "free" / "groq.json").exists()
    assert (tmp_path / "free" / "index.json").exists()
    assert "Reviewed free dataset" in stdout.getvalue()
