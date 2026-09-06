"""Tests for the strict call-time tool allowlist (SettingsModel.tool_call_allowlist).

DB-free by design: the detector is a pure helper and the decide_next_step
abort branch returns before any ORM touch, so these run without a test
database (which this env cannot build — pre-existing Django 4.2 vs 5.x
migration drift).
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from server.models.enums.message_enums import MessagePartType

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


ingest_mod = _load_script(".agentone/scripts/core/ingest_assistant_message.py")
decide_mod = _load_script(".agentone/scripts/core/decide_next_step.py")


def _toolcall(name, arguments=None):
    return {
        "type": MessagePartType.TOOLCALL,
        "content": {"name": name, "arguments": arguments or {}},
    }


def _message(text="hello"):
    return {"type": MessagePartType.MESSAGE, "content": text}


class TestAttemptedToolName:
    def test_plain_tool_returns_name(self):
        assert ingest_mod._attempted_tool_name(_toolcall("read", {"path": "x"})) == "read"

    def test_final_result_returns_name(self):
        assert ingest_mod._attempted_tool_name(_toolcall("final_result", {"content": "s"})) == "final_result"

    def test_catch_routes_to_embedded_original(self):
        part = _toolcall("catch_tool_argument_error", {"tool_name": "read", "arguments": {}, "error": "nope"})
        assert ingest_mod._attempted_tool_name(part) == "read"

    def test_catch_without_original_falls_back_loud(self):
        # Uninterpretable toolcall in a strict session must not slip through.
        assert ingest_mod._attempted_tool_name(_toolcall("catch_tool_argument_error", {})) == "catch_tool_argument_error"

    def test_approval_denial_is_not_an_attempt(self):
        assert ingest_mod._attempted_tool_name(_toolcall("catch_approval_denied", {})) is None


class TestAllowlistViolations:
    def test_final_result_only_is_clean(self):
        parts = [_toolcall("final_result", {"content": "summary"})]
        assert ingest_mod._allowlist_violations(parts, ["final_result"]) == []

    def test_stray_call_is_violation(self):
        parts = [_toolcall("final_result", {"content": "s"}), _toolcall("read", {"path": "x"})]
        assert ingest_mod._allowlist_violations(parts, ["final_result"]) == ["read"]

    def test_catch_rerouted_stray_call_is_violation(self):
        # Agent tried `read` (bad args) — the reroute must not launder it.
        parts = [_toolcall("catch_tool_argument_error", {"tool_name": "read", "arguments": {}, "error": "bad"})]
        assert ingest_mod._allowlist_violations(parts, ["final_result"]) == ["read"]

    def test_catch_rerouted_whitelisted_call_is_not_violation(self):
        # Soft validation retry for an allowed tool is preserved.
        parts = [_toolcall("catch_tool_argument_error", {"tool_name": "read", "arguments": {}, "error": "bad"})]
        assert ingest_mod._allowlist_violations(parts, ["final_result", "read"]) == []

    def test_empty_allowlist_allows_nothing(self):
        parts = [_toolcall("final_result", {"content": "s"})]
        assert ingest_mod._allowlist_violations(parts, []) == ["final_result"]

    def test_non_toolcall_parts_ignored(self):
        parts = [_message("please call read(path='x')"), {"type": "reasoning", "content": "thinking"}]
        assert ingest_mod._allowlist_violations(parts, ["final_result"]) == []

    def test_order_preserved_and_deduplicated(self):
        parts = [_toolcall("write", {}), _toolcall("read", {}), _toolcall("write", {})]
        assert ingest_mod._allowlist_violations(parts, ["final_result"]) == ["write", "read"]


class TestDecideAbortOnViolation:
    def _stub_session(self):
        calls: list = []

        def set_is_active(value):
            calls.append(("set_is_active", value))

        def count_turn():
            raise AssertionError("violating turn must not consume turn budget")

        def count_unattended_turn():
            raise AssertionError("violating turn must not consume turn budget")

        session = SimpleNamespace(
            set_is_active=set_is_active,
            count_turn=count_turn,
            count_unattended_turn=count_unattended_turn,
        )
        return session, calls

    def test_violation_deactivates_and_ends_turn(self):
        session, calls = self._stub_session()
        sentinel = object()
        out = decide_mod.decide_next_step(
            session, response=None, parts=[], message=sentinel,
            tool_allowlist_violated=["read"],
        )
        assert out is sentinel
        assert calls == [("set_is_active", False)]


class TestSettingsField:
    def test_tool_call_allowlist_field_exists_and_nullable(self):
        from django.db.models import JSONField
        from server.models.settings import SettingsModel
        field = SettingsModel._meta.get_field("tool_call_allowlist")
        assert isinstance(field, JSONField)
        assert field.null is True
        assert field.blank is True
        assert field.default is None
