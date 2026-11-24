"""Tests for leaderboard rank import/export and catalog preservation."""

from __future__ import annotations

import json
from pathlib import Path

from registry.catalog.ranks import (
    apply_ranks,
    clean_model_id,
    compute_leaderboard,
    export_markdown,
    match_leaderboard,
    parse_markdown,
    parse_rank_cell,
)
from registry.catalog.write import sync_dataset


def _write_model(root: Path, provider: str, slug: str, **extra) -> Path:
    path = root / "providers" / provider / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "_generated_by": "registry.catalog",
        "provider": provider,
        "model": slug,
        "name": extra.pop("name", slug.replace("-", " ").title()),
        "aliases": extra.pop("aliases", []),
        **extra,
    }
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def test_clean_model_id_strips_dates_and_throttle_suffixes():
    assert clean_model_id("GPT-6-Astra-20260101") == "GPT-6-Astra"
    assert clean_model_id("qwen3.8-max") == "qwen3.8-max"
    assert clean_model_id("glm-5.3-preview-20260201") == "glm-5.3"
    assert clean_model_id("claude-opus-5-5 (xHigh)") == "claude-opus-5-5"


def test_compute_leaderboard_is_deterministic_and_ranked():
    scores = {
        "alpha\tb1": [0.9],
        "beta\tb1": [0.1],
        "alpha\tb2": [0.8],
        "beta\tb2": [0.2],
    }
    first = compute_leaderboard(scores, {"alpha": "Alpha"})
    second = compute_leaderboard(scores, {"alpha": "Alpha"})
    assert first == second
    assert [row["Rank"] for row in first] == [1, 2]
    assert first[0]["Model ID"] == "alpha"
    assert first[0]["Name"] == "Alpha"


def test_match_leaderboard_prefers_best_rank_and_uses_aliases(tmp_path):
    _write_model(tmp_path, "z-ai", "glm-5-3", aliases=["glm-5.3-preview"])
    _write_model(tmp_path, "groq", "gpt-oss-120b", aliases=["openai/gpt-oss-120b"])
    rows = [
        {"Rank": 7, "Model ID": "glm-5.3"},
        {"Rank": 3, "Model ID": "GLM-5.3 Preview"},
        {"Rank": 11, "Model ID": "openai/gpt-oss-120b"},
        {"Rank": 99, "Model ID": "not-a-model"},
    ]

    matches = match_leaderboard(rows, tmp_path)

    assert matches["glm-5-3"]["rank"] == 3
    assert matches["gpt-oss-120b"]["rank"] == 11
    assert "not-a-model" not in matches


def test_parse_rank_cell_and_markdown_round_trip(tmp_path):
    assert parse_rank_cell("42") == 42
    assert parse_rank_cell("~120") == "~120"
    assert parse_rank_cell("") is None
    assert parse_rank_cell("nonsense") is None

    table = tmp_path / "model-ranks.md"
    table.write_text(
        "# Ranks\n\n| model_id | rank |\n|---|---|\n"
        "| alpha | 4 |\n| beta |  |\n| gamma | ~25 |\n",
        encoding="utf-8",
    )
    assert parse_markdown(table) == {"alpha": 4, "beta": None, "gamma": "~25"}


def test_apply_ranks_refresh_writes_all_provider_files_and_clears_blanks(tmp_path):
    first = _write_model(tmp_path, "a", "alpha", leaderboard_rank=999)
    second = _write_model(tmp_path, "b", "alpha")
    other = _write_model(tmp_path, "a", "beta", leaderboard_rank=12)

    matches = {"alpha": {"leaderboard_id": "Alpha-1", "leaderboard_rank": 5}}
    summary = apply_ranks(
        tmp_path,
        matches,
        {"alpha": None, "beta": None},
        clear_unranked=True,
    )

    assert summary["written"] == 3
    for path in (first, second):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["leaderboard_id"] == "Alpha-1"
        assert payload["leaderboard_rank"] == 5
        assert "leaderboard_rank_estimated" not in payload
    assert "leaderboard_rank" not in json.loads(other.read_text(encoding="utf-8"))


def test_apply_ranks_refresh_is_idempotent(tmp_path):
    _write_model(tmp_path, "a", "alpha")
    matches = {"alpha": {"leaderboard_id": "Alpha-1", "leaderboard_rank": 5}}

    first = apply_ranks(tmp_path, matches, {"alpha": 5}, clear_unranked=True)
    second = apply_ranks(tmp_path, matches, {"alpha": 5}, clear_unranked=True)

    assert first["written"] == 1
    assert second["written"] == 0
    payload = json.loads((tmp_path / "providers/a/alpha.json").read_text(encoding="utf-8"))
    assert payload["leaderboard_id"] == "Alpha-1"
    assert payload["leaderboard_rank"] == 5


def test_apply_ranks_import_only_touches_filled_cells(tmp_path):
    filled = _write_model(tmp_path, "a", "alpha", leaderboard_rank=7)
    untouched = _write_model(tmp_path, "b", "beta", leaderboard_rank=12)

    summary = apply_ranks(
        tmp_path,
        None,
        {"alpha": "~30", "beta": None},
        clear_unranked=False,
    )

    assert summary["written"] == 1
    alpha = json.loads(filled.read_text(encoding="utf-8"))
    assert alpha["leaderboard_rank_estimated"] == "~30"
    assert "leaderboard_rank" not in alpha
    assert json.loads(untouched.read_text(encoding="utf-8"))["leaderboard_rank"] == 12


def test_export_markdown_sorts_by_name_and_keeps_blanks(tmp_path):
    _write_model(tmp_path, "a", "zeta-model", name="Alpha Model")
    _write_model(tmp_path, "b", "alpha-model", name="Zulu Model")

    table = tmp_path / "model-ranks.md"
    rows = export_markdown(
        tmp_path,
        {"zeta-model": 4},
        {},
        table,
    )
    lines = table.read_text(encoding="utf-8").splitlines()
    data = [
        line
        for line in lines
        if line.startswith("| ") and not line.startswith("| model_id")
    ]

    assert rows == 2
    assert data == ["| zeta-model | 4 |", "| alpha-model |  |"]


def test_sync_model_ranks_command_imports_filled_cells(tmp_path):
    from io import StringIO  # pylint: disable=import-outside-toplevel

    from django.core.management import call_command  # pylint: disable=import-outside-toplevel

    model = _write_model(tmp_path, "a", "alpha")
    table = tmp_path / "model-ranks.md"
    table.write_text(
        "| model_id | rank |\n|---|---|\n| alpha | ~77 |\n",
        encoding="utf-8",
    )

    call_command(
        "sync_model_ranks",
        root=tmp_path,
        ranks_file=table,
        import_ranks=True,
        stdout=StringIO(),
    )

    payload = json.loads(model.read_text(encoding="utf-8"))
    assert payload["leaderboard_rank_estimated"] == "~77"
    assert "leaderboard_rank" not in payload


def test_export_markdown_sorts_by_vendor_free_model_name(tmp_path):
    _write_model(tmp_path, "a", "grok-3", name="xAI: Grok 3")
    _write_model(tmp_path, "b", "glm-5-3", name="zai-org/GLM-5.3")
    _write_model(tmp_path, "c", "alpha-model", name="Alpha Model (ElectronHub)")

    table = tmp_path / "model-ranks.md"
    export_markdown(tmp_path, {}, {}, table)
    rows = [
        line.split("|")[1].strip()
        for line in table.read_text(encoding="utf-8").splitlines()
        if line.startswith("| ") and not line.startswith("| model_id")
    ]

    assert rows == ["alpha-model", "glm-5-3", "grok-3"]


def test_catalog_regeneration_preserves_rank_fields(tmp_path):
    model = _write_model(
        tmp_path,
        "a",
        "alpha",
        leaderboard_id="Alpha-1",
        leaderboard_rank=4,
        leaderboard_rank_estimated="~3",
    )
    before = json.loads(model.read_text(encoding="utf-8"))
    expected_model = {
        "_generated_by": "registry.catalog",
        "provider": "a",
        "model": "alpha",
        "name": "Alpha Model",
    }
    sync_dataset(
        {"a": {"_generated_by": "registry.catalog", "provider": "a", "name": "A"}},
        {("a", "alpha"): expected_model},
        tmp_path,
        dry_run=False,
    )
    after = json.loads(model.read_text(encoding="utf-8"))

    for field in ("leaderboard_id", "leaderboard_rank", "leaderboard_rank_estimated"):
        assert after[field] == before[field]
