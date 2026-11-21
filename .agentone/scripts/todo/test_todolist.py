"""Tests for the session todo tool (``todolist.py``).

State is event-sourced from the ``todolist_action`` anchor history: each
action replays against the previous payload and stores the full item list.
These tests pin that replay contract, the ``[True, payload]`` envelope
unwrap, and the read-only/paginated behaviour of ``todo_list``.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from todolist import (  # pylint: disable=wrong-import-position
    _coerce_task_id,
    _coerce_task_ids,
    _load_todolist_items,
    todolist_action,
    todolist_action_response,
    todo_append,
    todo_clear,
    todo_command,
    todo_delete,
    todo_list,
    todo_update,
)


class _ActionSession:
    """Minimal session view used while replaying an anchor action."""

    def __init__(self, anchor):
        self.anchor = anchor

    def get_task(self, name):
        return self.anchor if name == "todolist_action" else None


class FakeAnchor:
    """Simulates the ``todolist_action`` history: delay() replays synchronously.

    lastest_result() returns the enveloped ``[True, payload]`` pair, exactly
    like AgentTaskCall.get_result() in production — an unwrapped fake once
    hid a real empty-list bug.
    """

    def __init__(self):
        self.history: list[dict] = []
        self.session = _ActionSession(self)

    def lastest_result(self):
        return [True, self.history[-1]] if self.history else None

    def delay(self, action, **params):
        result = todolist_action(self.session, action, **params)
        self.history.append(result)
        return result


class FakeResolver:
    """Slim anchor resolver: drops the full item list from the tool result."""

    def delay(self, store_function_response):
        return True, todolist_action_response(None, store_function_response)


class StubSession:
    """Minimal stand-in for Session (anchor history + slim resolver)."""

    def __init__(self):
        self.anchor = FakeAnchor()
        self.resolver = FakeResolver()

    def get_task(self, name):
        if name == "todolist_action":
            return self.anchor
        if name == "todolist_action_response":
            return self.resolver
        return None

    def get_tool(self, name):
        return None


def apply_action(session, action, **params):
    """Replay one anchor action and return the raw store-call payload."""
    return session.anchor.delay(action, **params)


class TestTodoActions(unittest.TestCase):
    """Tests for the pure anchor state transitions (no DB needed)."""

    def test_append_assigns_sequential_task_ids(self) -> None:
        session = StubSession()
        result = apply_action(session, "append", text="first")
        self.assertEqual(result["message"], "task 1 created")
        self.assertEqual(result["items"][0]["text"], "first")
        self.assertEqual(result["items"][0]["status"], "pending")
        result = apply_action(session, "append", text="second", depends_on=1)
        self.assertEqual(result["items"][1]["task_id"], 2)
        self.assertEqual(result["items"][1]["depends_on"], 1)

    def test_append_without_text_still_creates_an_item(self) -> None:
        result = apply_action(StubSession(), "append")
        self.assertEqual(len(result["items"]), 1)
        self.assertNotIn("text", result["items"][0])

    def test_update_changes_only_requested_fields(self) -> None:
        session = StubSession()
        apply_action(session, "append", text="a", depends_on=1)
        result = apply_action(session, "update", task_id=1, status="in_progress")
        self.assertEqual(result["items"][0]["text"], "a")
        self.assertEqual(result["items"][0]["depends_on"], 1)
        self.assertEqual(result["items"][0]["status"], "in_progress")

    def test_update_missing_id_is_reported(self) -> None:
        result = apply_action(StubSession(), "update", task_id=99, status="completed")
        self.assertIn("no task with task_id", result["message"])
        self.assertEqual(result["items"], [])

    def test_delete_accepts_one_id_a_list_or_csv(self) -> None:
        for selector in (1, [1], "1"):
            session = StubSession()
            apply_action(session, "append", text="a")
            result = apply_action(session, "delete", task_ids=selector)
            self.assertEqual(result["items"], [])
            self.assertIn("1 of 1 tasks deleted", result["message"])

    def test_delete_without_selector_removes_nothing(self) -> None:
        session = StubSession()
        apply_action(session, "append", text="a")
        result = apply_action(session, "delete")
        self.assertEqual([i["text"] for i in result["items"]], ["a"])

    def test_clear_drops_every_item(self) -> None:
        session = StubSession()
        apply_action(session, "append", text="a")
        result = apply_action(session, "clear")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["message"], "1 tasks deleted")

    def test_unknown_action_is_reported(self) -> None:
        result = apply_action(StubSession(), "explode")
        self.assertIn("Unknown action", result["message"])
        self.assertEqual(result["items"], [])

    def test_id_coercion_helpers(self) -> None:
        self.assertEqual(_coerce_task_id("3"), 3)
        self.assertIsNone(_coerce_task_id("nope"))
        self.assertEqual(_coerce_task_ids([1, "2", "x", None]), {1, 2})
        self.assertEqual(_coerce_task_ids("1,2"), {1, 2})
        self.assertEqual(_coerce_task_ids(None), set())

    def test_envelope_unwrap(self) -> None:
        session = StubSession()
        self.assertEqual(_load_todolist_items(session), [])
        apply_action(session, "append", text="a")
        self.assertEqual(
            [item["text"] for item in _load_todolist_items(session)], ["a"]
        )


class TestTodoTools(unittest.TestCase):
    """Tests for the tool functions against a stub session."""

    def test_append_list_update_delete_clear_flow(self) -> None:
        session = StubSession()
        ok, result = todo_append(session, "a")
        self.assertTrue(ok)
        self.assertEqual(result["action"], "append")
        self.assertIn("task 1 created", result["message"])
        todo_append(session, "b")

        ok, result = todo_list(session, limit=10)
        self.assertTrue(ok)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["message"], "Matched 2 of 2 items, 2 shown")

        ok, _ = todo_update(session, 1, status="in_progress")
        self.assertTrue(ok)
        ok, _ = todo_update(session, 1, status="completed")
        self.assertTrue(ok)
        self.assertEqual(_load_todolist_items(session)[0]["status"], "completed")

        ok, result = todo_delete(session, task_ids=2)
        self.assertTrue(ok)
        self.assertIn("1 of 2 tasks deleted", result["message"])

        ok, result = todo_clear(session)
        self.assertTrue(ok)
        self.assertEqual(result["action"], "clear")
        self.assertEqual(_load_todolist_items(session), [])

    def test_list_filters_and_pagination(self) -> None:
        session = StubSession()
        for text in ("alpha", "beta", "gamma"):
            todo_append(session, text)
        todo_update(session, 2, status="completed")

        _, result = todo_list(session, status="completed", limit=10)
        self.assertEqual([i["text"] for i in result["items"]], ["beta"])
        _, result = todo_list(session, search_text="a", limit=2, offset=1)
        self.assertEqual([i["text"] for i in result["items"]], ["beta", "gamma"])
        self.assertEqual(result["message"], "Matched 3 of 3 items, 2 shown")

    def test_list_is_read_only(self) -> None:
        session = StubSession()
        todo_append(session, "a")
        recorded = len(session.anchor.history)
        todo_list(session)
        todo_list(session, limit=10)
        self.assertEqual(len(session.anchor.history), recorded)

    def test_resolver_drops_the_full_item_list(self) -> None:
        session = StubSession()
        _, result = todo_append(session, "a")
        self.assertNotIn("items", result)
        self.assertEqual(set(result), {"action", "message"})

    def test_state_survives_across_tool_calls(self) -> None:
        session = StubSession()
        todo_append(session, "a")
        todo_append(session, "b")
        stored = _load_todolist_items(session)
        self.assertEqual([i["text"] for i in stored], ["a", "b"])
        self.assertEqual(_load_todolist_items(session), stored)

    def test_command_is_a_user_only_noop(self) -> None:
        session = StubSession()
        self.assertIsNone(todo_command(session))
        self.assertIsNone(todo_command(session, action="clear"))
        self.assertEqual(_load_todolist_items(session), [])


if __name__ == "__main__":
    unittest.main()
