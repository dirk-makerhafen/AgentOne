"""Tests for the core ``map`` batch task (``.agentone/scripts/core/map.py``)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from map import map as map_task  # noqa: E402


class _FakeCall:
    def __init__(self, args, kwargs, limit):
        self.args = args
        self.kwargs = kwargs
        self.limit = limit


class _FakeTaskInstance:
    def __init__(self):
        self.calls: list[_FakeCall] = []

    def apply_async(self, args=None, kwargs=None, **options):
        call = _FakeCall(args, kwargs, options.get("limit_per_instance_parallel_runs"))
        self.calls.append(call)
        return call


class _FakeBoundTask:
    def __init__(self, name: str):
        self.name = name
        self.task_instance = _FakeTaskInstance()
        self.instance_count = 0

    def instance(self):
        self.instance_count += 1
        return self.task_instance


class _FakeSession:
    """Minimal stand-in for ``runtime.session.session.Session``."""

    def __init__(self, tasks=None, tools=None, commands=None):
        self._by_kind = {
            "task": tasks or {},
            "tool": tools or {},
            "command": commands or {},
        }
        self.allowedTaskNames = sorted(self._by_kind["task"])
        self.allowedToolNames = sorted(self._by_kind["tool"])
        self.allowedCommandNames = sorted(self._by_kind["command"])

    def get_task(self, name):
        return self._by_kind["task"].get(name)

    def get_tool(self, name):
        return self._by_kind["tool"].get(name)

    def get_command(self, name):
        return self._by_kind["command"].get(name)


class TestResolution(unittest.TestCase):
    def test_prefers_task_over_tool_and_command(self):
        task, tool, command = _FakeBoundTask("x"), _FakeBoundTask("x"), _FakeBoundTask("x")
        session = _FakeSession(tasks={"x": task}, tools={"x": tool}, commands={"x": command})

        map_task(session, "x", [{"a": 1}])

        self.assertEqual(task.task_instance.calls[0].kwargs, {"a": 1})
        self.assertEqual(tool.task_instance.calls, [])
        self.assertEqual(command.task_instance.calls, [])

    def test_falls_back_to_tool(self):
        tool = _FakeBoundTask("x")
        result = map_task(_FakeSession(tools={"x": tool}), "x", [{}])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(tool.task_instance.calls), 1)

    def test_falls_back_to_command(self):
        command = _FakeBoundTask("x")
        result = map_task(_FakeSession(commands={"x": command}), "x", [{}])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(command.task_instance.calls), 1)

    def test_explicit_kind_skips_higher_precedence_kinds(self):
        task, tool = _FakeBoundTask("x"), _FakeBoundTask("x")
        session = _FakeSession(tasks={"x": task}, tools={"x": tool})

        map_task(session, "x", [{}], kind="tool")

        self.assertEqual(len(tool.task_instance.calls), 1)
        self.assertEqual(task.task_instance.calls, [])

    def test_explicit_kind_rejects_when_not_allowed_as_that_kind(self):
        session = _FakeSession(tools={"x": _FakeBoundTask("x")})
        with self.assertRaises(ValueError) as ctx:
            map_task(session, "x", [{}], kind="task")
        self.assertIn("task 'x' is not available", str(ctx.exception))
        self.assertIn("Allowed tasks", str(ctx.exception))

    def test_unknown_target_lists_allowed_names(self):
        session = _FakeSession(
            tasks={"a_task": _FakeBoundTask("a_task")},
            tools={"a_tool": _FakeBoundTask("a_tool")},
            commands={"a_command": _FakeBoundTask("a_command")},
        )
        with self.assertRaises(ValueError) as ctx:
            map_task(session, "nope", [{}])
        msg = str(ctx.exception)
        self.assertIn("'nope'", msg)
        self.assertIn("a_task", msg)
        self.assertIn("a_tool", msg)
        self.assertIn("a_command", msg)

    def test_invalid_kind_raises(self):
        with self.assertRaises(ValueError) as ctx:
            map_task(_FakeSession(tasks={"x": _FakeBoundTask("x")}), "x", [{}], kind="function")
        self.assertIn("unknown kind", str(ctx.exception))


class TestDispatch(unittest.TestCase):
    def test_dict_items_become_kwargs_and_scalars_positional(self):
        bound = _FakeBoundTask("x")
        map_task(_FakeSession(tasks={"x": bound}), "x", [{"path": "a.md"}, "b.md"])

        first, second = bound.task_instance.calls
        self.assertEqual(first.kwargs, {"path": "a.md"})
        self.assertIsNone(first.args)
        self.assertEqual(second.args, ["b.md"])
        self.assertIsNone(second.kwargs)

    def test_all_items_share_one_task_instance(self):
        bound = _FakeBoundTask("x")
        map_task(_FakeSession(tasks={"x": bound}), "x", [{"i": 1}, {"i": 2}, {"i": 3}])
        self.assertEqual(bound.instance_count, 1)

    def test_default_concurrency_is_one(self):
        bound = _FakeBoundTask("x")
        map_task(_FakeSession(tasks={"x": bound}), "x", [{"i": 1}, {"i": 2}])
        self.assertEqual([c.limit for c in bound.task_instance.calls], [1, 1])

    def test_concurrency_is_forwarded_per_call(self):
        bound = _FakeBoundTask("x")
        map_task(_FakeSession(tasks={"x": bound}), "x", [{"i": 1}, {"i": 2}], concurrency=3)
        self.assertEqual([c.limit for c in bound.task_instance.calls], [3, 3])

    def test_zero_concurrency_is_forwarded(self):
        bound = _FakeBoundTask("x")
        map_task(_FakeSession(tasks={"x": bound}), "x", [{"i": 1}], concurrency=0)
        self.assertEqual(bound.task_instance.calls[0].limit, 0)

    def test_returns_calls_in_input_order(self):
        bound = _FakeBoundTask("x")
        result = map_task(
            _FakeSession(tasks={"x": bound}), "x", [{"i": 1}, {"i": 2}, {"i": 3}]
        )
        self.assertEqual(result, bound.task_instance.calls)

    def test_non_list_items_raise(self):
        bound = _FakeBoundTask("x")
        session = _FakeSession(tasks={"x": bound})
        with self.assertRaises(ValueError) as ctx:
            map_task(session, "x", "a.md")
        self.assertIn("list or tuple", str(ctx.exception))
        self.assertEqual(bound.instance_count, 0)

    def test_empty_list_returns_empty_and_does_not_resolve(self):
        bound = _FakeBoundTask("x")
        session = _FakeSession(tasks={"x": bound})
        self.assertEqual(map_task(session, "x", []), [])
        self.assertEqual(map_task(session, "x", None), [])
        self.assertEqual(bound.instance_count, 0)


if __name__ == "__main__":
    unittest.main()
