from pathlib import Path

from runtime import tool_result_budget as budget


def test_preview_snaps_to_newline():
    content = "first line\nsecond line\nthird line\n" + "x" * 100
    preview, has_more = budget.generate_preview(content, max_chars=30)
    assert has_more
    assert preview.endswith("\n")
    assert len(preview) <= 30


def test_persist_oversized_result(tmp_path: Path):
    content = "line one\n" + "y" * 30_000
    replacement = budget.persist_tool_result(
        content, "webFetch", "tc-123", storage_dir=tmp_path
    )

    assert budget.PERSISTED_OUTPUT_TAG in replacement
    assert str(tmp_path) in replacement
    assert "filesystem.read" in replacement
    assert "line one" in replacement
    saved = list(tmp_path.glob("*.txt"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == content


def test_small_result_is_not_persisted(tmp_path: Path):
    content = "short result"
    assert budget.persist_tool_result(content, "grep", "tc-1", storage_dir=tmp_path) == content
    assert not list(tmp_path.glob("*.txt"))


def test_read_tool_is_pinned(tmp_path: Path):
    content = "z" * 50_000
    assert budget.persist_tool_result(content, "filesystem.read", "tc-2", storage_dir=tmp_path) == content
    assert not list(tmp_path.glob("*.txt"))


def test_persist_without_storage_falls_back_to_inline_truncation(monkeypatch):
    monkeypatch.delenv("AGENTONE_SESSION_DIR", raising=False)
    content = "q" * 30_000
    replacement = budget.persist_tool_result(content, "shell", "tc-3", storage_dir=None)
    assert "[Truncated:" in replacement
    assert "no session storage" in replacement
    assert len(replacement) < len(content)


def test_turn_budget_spills_largest_results(tmp_path: Path):
    large_a = "a" * 30_000
    large_b = "b" * 25_000
    small = "c" * 1_000
    messages = [
        {"role": "tool", "tool_call_id": "tc-1", "content": large_a},
        {"role": "tool", "tool_call_id": "tc-2", "content": large_b},
        {"role": "tool", "tool_call_id": "tc-3", "content": small},
        {"role": "tool", "tool_call_id": "tc-4", "content": [
            {"type": "text", "text": "image result"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        ]},
    ]

    budget.enforce_turn_budget(messages, storage_dir=tmp_path, budget=10_000)

    assert budget.PERSISTED_OUTPUT_TAG in messages[0]["content"]
    assert budget.PERSISTED_OUTPUT_TAG in messages[1]["content"]
    assert messages[2]["content"] == small
    assert isinstance(messages[3]["content"], list)
    saved = list(tmp_path.glob("*.txt"))
    assert len(saved) == 2
    assert sum(len(m["content"]) for m in messages if isinstance(m["content"], str)) <= 10_000
