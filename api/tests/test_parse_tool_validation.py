"""Tests for tool-call argument validation in parse_llm_response:

- scalar coercion (int/float/bool from strings the LLM emits)
- routing invalid calls to ``catch_tool_argument_error``
- unknown / disallowed tools are routed to the catch tool
- ``final_result`` and the catch tool itself are never re-validated
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.settings import AgentToolCallSyntax

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


parse_mod = _load_script(".agentone/scripts/core/parse_llm_response.py")


class FakeBoundTask:
    def __init__(self, schema):
        self.task_definition_version = SimpleNamespace(function_schema=schema)


class FakeSession:
    def __init__(self, tools):
        self.tools = tools
        self.tool_call_syntax = AgentToolCallSyntax.DEFAULT
        self.model = SimpleNamespace(pk=1)

    def get_tool(self, name):
        task = self.tools.get(name)
        if task is None:
            return None
        if isinstance(task, FakeBoundTask):
            return task
        return FakeBoundTask(task)


def _tool(name, schema):
    return {name: schema}


def _call(name, arguments):
    return {"id": f"custom_{name}", "function": {"name": name, "arguments": arguments}}


@pytest.mark.django_db
class TestValidateToolCall:
    def test_integer_coercion(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}},
            "required": ["path"],
        }))
        name, args, error = parse_mod._validate_tool_call(session, "read", {"path": "x.txt", "offset": "10"})
        assert name == "read"
        assert error is None
        assert args == {"path": "x.txt", "offset": 10}

    def test_number_coercion(self):
        session = FakeSession(_tool("measure", {
            "type": "object",
            "properties": {"ratio": {"type": "number"}},
            "required": ["ratio"],
        }))
        name, args, error = parse_mod._validate_tool_call(session, "measure", {"ratio": "0.75"})
        assert name == "measure"
        assert args == {"ratio": 0.75}
        assert error is None

    def test_boolean_coercion(self):
        session = FakeSession(_tool("flag", {
            "type": "object",
            "properties": {"blocking": {"type": "boolean"}},
        }))
        _, args, error = parse_mod._validate_tool_call(session, "flag", {"blocking": "true"})
        assert error is None
        assert args == {"blocking": True}
        _, args, error = parse_mod._validate_tool_call(session, "flag", {"blocking": "FALSE"})
        assert error is None
        assert args == {"blocking": False}

    def test_unknown_tool_routes_to_catch(self):
        session = FakeSession({})
        name, args, error = parse_mod._validate_tool_call(session, "does_not_exist", {"a": 1})
        assert name == "catch_tool_argument_error"
        assert error is not None
        assert args["tool_name"] == "does_not_exist"
        assert args["arguments"] == {"a": 1}

    def test_invalid_integer_routes_to_catch(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}},
        }))
        name, args, error = parse_mod._validate_tool_call(session, "read", {"path": "x", "offset": "abc"})
        assert name == "catch_tool_argument_error"
        assert "offset" in error
        assert args["tool_name"] == "read"

    def test_missing_required_routes_to_catch(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }))
        name, args, error = parse_mod._validate_tool_call(session, "read", {})
        assert name == "catch_tool_argument_error"
        assert "path" in error

    def test_required_with_default_is_not_an_error(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "limit": {"type": "integer", "default": 100}},
            "required": ["path", "limit"],
        }))
        name, args, error = parse_mod._validate_tool_call(session, "read", {"path": "x"})
        assert name == "read"
        assert error is None

    def test_final_result_never_validated(self):
        session = FakeSession({})
        name, args, error = parse_mod._validate_tool_call(session, "final_result", {"content": "done"})
        assert name == "final_result"
        assert error is None

    def test_catch_tool_never_revalidated(self):
        session = FakeSession({})
        name, args, error = parse_mod._validate_tool_call(
            session, "catch_tool_argument_error", {"tool_name": "read", "arguments": {}}
        )
        assert name == "catch_tool_argument_error"
        assert error is None

    def test_non_dict_arguments_routes_to_catch(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }))
        name, args, error = parse_mod._validate_tool_call(session, "read", "not-a-dict")
        assert name == "catch_tool_argument_error"
        assert args["tool_name"] == "read"


@pytest.mark.django_db
class TestCatchToolArgumentError:
    def test_returns_error_message(self):
        mod = _load_script(".agentone/scripts/core/catch_tool_argument_error.py")
        ok, result = mod.catch_tool_argument_error(
            None, "read", {"path": "x", "offset": "abc"}, "argument 'offset' must be a integer"
        )
        assert ok is False
        assert result["status"] == "error"
        assert "read" in result["message"]
        assert "offset" in result["message"]
        assert result["message"].startswith("Tool 'read' was NOT executed")

    def test_error_defaults(self):
        mod = _load_script(".agentone/scripts/core/catch_tool_argument_error.py")
        ok, result = mod.catch_tool_argument_error(None, "read", {"a": 1})
        assert ok is False
        assert "unknown validation failure" in result["message"]


@pytest.mark.django_db
class TestParseLlMResponseValidation:
    def _response(self, tool_calls, content="", reasoning=""):
        return SimpleNamespace(tool_calls=tool_calls, content=content, reasoning=reasoning)

    def test_default_syntax_invalid_call_is_routed(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}},
        }))
        response = self._response([_call("read", {"path": "x", "offset": "abc"})])
        result = parse_mod.parse_llm_response(session, response)
        parts = [p for p in result["parts"] if p["type"] == MessagePartType.TOOLCALL]
        assert len(parts) == 1
        content = parts[0]["content"]
        assert content["name"] == "catch_tool_argument_error"
        assert content["arguments"]["tool_name"] == "read"
        assert "offset" in content["arguments"]["error"]

    def test_default_syntax_integer_coerced(self):
        session = FakeSession(_tool("read", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}},
            "required": ["path"],
        }))
        response = self._response([_call("read", {"path": "x", "offset": "5"})])
        result = parse_mod.parse_llm_response(session, response)
        parts = [p for p in result["parts"] if p["type"] == MessagePartType.TOOLCALL]
        content = parts[0]["content"]
        assert content["name"] == "read"
        assert content["arguments"] == {"path": "x", "offset": 5}

    def test_custom_syntax_routes_bad_types(self):
        session = FakeSession(_tool("tree", {
            "type": "object",
            "properties": {"path": {"type": "string"}, "depth": {"type": "integer"}},
        }))
        session.tool_call_syntax = AgentToolCallSyntax.CUSTOM
        response = self._response([], content='[call:tree(path=".", depth=not_a_number)]')
        result = parse_mod.parse_llm_response(session, response)
        toolcall_parts = [p for p in result["parts"] if p["type"] == MessagePartType.TOOLCALL]
        assert len(toolcall_parts) == 1
        content = toolcall_parts[0]["content"]
        assert content["name"] == "catch_tool_argument_error"
        assert content["arguments"]["tool_name"] == "tree"

    def test_final_result_passes_through_unvalidated(self):
        session = FakeSession({})
        response = self._response([_call("final_result", {"content": "all done"})])
        result = parse_mod.parse_llm_response(session, response)
        toolcall_parts = [p for p in result["parts"] if p["type"] == MessagePartType.TOOLCALL]
        assert len(toolcall_parts) == 1
        assert toolcall_parts[0]["content"]["name"] == "final_result"
