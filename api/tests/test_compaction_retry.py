"""Tests for the immediate bounded compaction retry.

DB-free by design: only the pure attempt-budget helper is exercised here
(the chain functions need a database, which this env cannot build —
pre-existing Django 4.2 vs 5.x migration drift).
"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relpath: str):
    """Load a manifest script module the same way registry/loader does."""
    spec = importlib.util.spec_from_file_location(
        relpath.replace("/", "_").replace(".", "_"),
        _ROOT / relpath,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


ingest_mod = _load_script(".agentone/scripts/compact/ingest_compaction.py")
decide_mod = _load_script(".agentone/scripts/core/decide_next_step.py")


class TestCompactRetryBudget:
    def test_budget_is_three_total_attempts(self):
        assert ingest_mod.MAX_COMPACT_ATTEMPTS == 3

    def test_first_failure_retries_as_attempt_one(self):
        assert ingest_mod._next_compact_attempt(0) == 1

    def test_second_failure_retries_as_attempt_two(self):
        assert ingest_mod._next_compact_attempt(1) == 2

    def test_third_failure_exhausts_budget(self):
        assert ingest_mod._next_compact_attempt(2) is None

    def test_over_budget_stays_exhausted(self):
        assert ingest_mod._next_compact_attempt(5) is None

    def test_garbage_attempt_counts_as_fresh(self):
        assert ingest_mod._next_compact_attempt("bad") == 1
        assert ingest_mod._next_compact_attempt(None) == 1


class TestCompactionResponseWrapper:
    """ingest_compaction_response reshapes the awaited retry result into the
    old success shape (response/parts/message) without touching the DB."""

    def test_dict_result_unpacks_marker(self):
        marker, response = object(), object()
        parts = [{"type": "text"}]
        out = ingest_mod.ingest_compaction_response(
            None,
            compaction_result={"message": marker},
            response=response,
            parts=parts,
            message=object(),
            compact_attempt=1,
        )
        assert out["message"] is marker
        assert out["response"] is response
        assert out["parts"] == parts
        assert out["compaction_retried"] is True
        assert out["compact_attempt"] == 1

    def test_missing_marker_falls_back_to_carried_message(self):
        carried = object()
        out = ingest_mod.ingest_compaction_response(
            None, compaction_result={}, response=None, parts=None, message=carried
        )
        assert out["message"] is carried

    def test_none_result_falls_back_to_carried_message(self):
        carried = object()
        out = ingest_mod.ingest_compaction_response(None, compaction_result=None, message=carried)
        assert out["message"] is carried
        assert out["response"] is None

    def test_wrapper_carries_parent_message_and_flags(self):
        parent = object()
        out = ingest_mod.ingest_compaction_response(
            None,
            compaction_result={"message": object()},
            response=None,
            parts=None,
            message=object(),
            parent_message=parent,
            has_final_result=True,
            tool_allowlist_violated=["shell"],
            compact_attempt=1,
        )
        assert out["parent_message"] is parent
        assert out["has_final_result"] is True
        assert out["tool_allowlist_violated"] == ["shell"]


class TestPersistedPartsFallback:
    """decide_next_step rebuilds the turn from the parent message when the
    retry-flattened resume arrives with parts=None (see parts_vs_message.md
    §8).  DB-free: the helper only needs a message-like with
    ``parts.order_by``."""

    def _fake_msg(self, parts):
        from types import SimpleNamespace

        class FakeQS(list):
            def order_by(self, *args):
                return list(self)

        return SimpleNamespace(parts=FakeQS(parts))

    def _fake_part(self, type, content="", tool_call=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            type=type,
            content=SimpleNamespace(get=lambda: content) if content is not None else None,
            tool_call=tool_call,
        )

    def test_toolcall_key_present_only_when_attached(self):
        from server.models.enums.message_enums import MessagePartType

        call = object()
        out = decide_mod._persisted_parts_dicts(self._fake_msg([
            self._fake_part(MessagePartType.MESSAGE, "hi"),
            self._fake_part(MessagePartType.TOOLCALL, {}, tool_call=call),
        ]))
        assert out[0] == {"type": MessagePartType.MESSAGE, "content": "hi"}
        assert out[1]["tool_call"] is call

    def test_missing_content_reads_as_empty(self):
        from server.models.enums.message_enums import MessagePartType

        out = decide_mod._persisted_parts_dicts(self._fake_msg([
            self._fake_part(MessagePartType.MESSAGE, None),
        ]))
        assert out == [{"type": MessagePartType.MESSAGE, "content": ""}]

    def test_unusable_message_reads_as_empty(self):
        assert decide_mod._persisted_parts_dicts(None) == []
        assert decide_mod._persisted_parts_dicts(object()) == []


class TestDecideTurnShapeFlags:
    """DB-free: decide prefers the ingest flags over recomputing from parts."""

    def _session(self, process_turn=None):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from server.models.enums.session_enums import SessionType

        return SimpleNamespace(
            count_turn=lambda: None,
            count_unattended_turn=lambda: None,
            max_turns=None,
            max_unattended_turns=None,
            current_turn_count=0,
            current_unattended_turn_count=0,
            session_type=SessionType.SESSION,
            _get_session_setting=lambda name: False,
            get_task=lambda name: process_turn
            if name == "process_turn" else MagicMock(),
        )

    def _assistant_message(self):
        from types import SimpleNamespace

        from server.models.enums.message_enums import MessageRole

        return SimpleNamespace(
            role=MessageRole.ASSISTANT,
            response=SimpleNamespace(tool_calls=[object()]),
            prev_message=None,
        )

    def test_flags_win_over_parts(self):
        from unittest.mock import MagicMock

        from server.models.enums.message_enums import MessagePartType

        process_turn = MagicMock()
        parts = [
            {"type": MessagePartType.TOOLCALL, "content": {},
             "tool_call": object()},
            {"type": MessagePartType.MESSAGE, "content": "Done?"},
        ]
        out = decide_mod.decide_next_step(
            self._session(process_turn), None, parts,
            self._assistant_message(),
            has_tool_calls=False, has_message=True,
        )
        assert out is not None
        process_turn.delay.assert_not_called()

    def test_missing_flags_fall_back_to_parts(self):
        from unittest.mock import MagicMock

        from server.models.enums.message_enums import MessagePartType

        process_turn = MagicMock()
        parts = [
            {"type": MessagePartType.TOOLCALL, "content": {},
             "tool_call": object()},
            {"type": MessagePartType.MESSAGE, "content": "Done?"},
        ]
        decide_mod.decide_next_step(
            self._session(process_turn), None, parts,
            self._assistant_message(),
        )
        process_turn.delay.assert_called_once()
