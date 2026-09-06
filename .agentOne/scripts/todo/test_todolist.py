import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from todolist import (
    apply_todo_action,
    coerce_items,
    is_todo_auto,
    load_todo_items,
    set_todo_auto,
    todo_append,
    todo_clear,
    todo_command,
    todo_done,
    todo_list,
    todo_peek,
    todo_pop,
    todo_remove,
)


class FakeAnchor:
    """Simulates the todolist_action history: delay() replays synchronously.

    lastest_result() returns the enveloped ``[True, payload]`` pair, exactly
    like AgentTaskCall.get_result() in production — this guards the unwrap
    path (an unwrapped fake once hid a real empty-list bug).
    """

    def __init__(self):
        self.history: list[dict] = []

    def lastest_result(self):
        return [True, self.history[-1]] if self.history else None

    def delay(self, action="list", **params):
        prev = self.history[-1]["items"] if self.history else []
        items, extra = apply_todo_action(prev, action, **params)
        result = {"status": "success", "action": action, "items": items}
        result.update(extra)
        self.history.append(result)
        return result
    
class StubSession:
    """Minimal stand-in for Session (anchor history + settings flag)."""

    def __init__(self):
        self.anchor = FakeAnchor()
        self.settings = {}

    def get_task(self, name):
        return self.anchor if name == "todolist_action" else None

    def get_tool(self, name):
        return None

    def _get_session_setting(self, name):
        return self.settings.get(name)

    def _set_session_setting(self, name, value):
        self.settings[name] = value


class TestTodoActions(unittest.TestCase):
    """Tests for the pure todo state transitions (no DB needed)."""

    def test_append_single_and_multiple(self) -> None:
        items, extra = apply_todo_action([], "append", text="first")
        self.assertEqual(len(extra["added"]), 1)
        self.assertEqual(extra["added"][0]["id"], 1)
        items, extra = apply_todo_action(items, "append", texts=["second", "third"])
        self.assertEqual([i["id"] for i in items], [1, 2, 3])
        self.assertEqual(extra["pending"], 3)

    def test_append_requires_text(self) -> None:
        with self.assertRaises(ValueError):
            apply_todo_action([], "append")

    def test_pop_marks_done_fifo(self) -> None:
        items, _ = apply_todo_action([], "append", texts=["a", "b", "c"])
        items, extra = apply_todo_action(items, "pop", count=2)
        self.assertEqual([i["text"] for i in extra["popped"]], ["a", "b"])
        self.assertEqual(extra["pending"], 1)
        self.assertEqual(items[0]["status"], "done")

    def test_pop_empty_succeeds(self) -> None:
        items, extra = apply_todo_action([], "pop")
        self.assertEqual(extra["popped"], [])
        self.assertEqual(extra["pending"], 0)

    def test_peek_does_not_mutate(self) -> None:
        items, _ = apply_todo_action([], "append", texts=["a", "b"])
        before = [dict(i) for i in items]
        items, extra = apply_todo_action(items, "peek", count=2)
        self.assertEqual([i["text"] for i in extra["selection"]], ["a", "b"])
        self.assertEqual(items, before)

    def test_done_and_remove_by_id(self) -> None:
        items, _ = apply_todo_action([], "append", texts=["a", "b"])
        items, extra = apply_todo_action(items, "done", ids=[1])
        self.assertEqual(len(extra["updated"]), 1)
        self.assertEqual(extra["pending"], 1)
        items, extra = apply_todo_action(items, "remove", ids=2)
        self.assertEqual(extra["removed"], 1)
        self.assertEqual(len(items), 1)

    def test_clear_pending_keeps_done(self) -> None:
        items, _ = apply_todo_action([], "append", texts=["a", "b"])
        items, _ = apply_todo_action(items, "pop", count=1)
        items, extra = apply_todo_action(items, "clear")
        self.assertEqual(extra["cleared"], 1)
        self.assertEqual(len(items), 1)
        items, _ = apply_todo_action(items, "clear", include_done=True)
        self.assertEqual(items, [])

    def test_list_pagination(self) -> None:
        items, _ = apply_todo_action([], "append", texts=["a", "b", "c"])
        _, extra = apply_todo_action(items, "list", limit=2, offset=1)
        self.assertEqual([i["text"] for i in extra["selection"]], ["b", "c"])
        self.assertEqual(extra["total"], 3)

    def test_unknown_action(self) -> None:
        with self.assertRaises(ValueError):
            apply_todo_action([], "explode")

    def test_coerce_malformed(self) -> None:
        self.assertEqual(coerce_items(None), [])
        self.assertEqual(coerce_items("nope"), [])
        self.assertEqual(coerce_items([{"id": 1, "text": "x"}])[0]["status"], "pending")
        self.assertEqual(coerce_items([{"id": 1, "text": "  "}]), [])


class TestTodoTools(unittest.TestCase):
    """Tests for the tool functions against a stub session."""

    def test_append_list_pop_flow(self) -> None:
        s = StubSession()
        ok, res = todo_append(s, texts=["a", "b"])
        self.assertTrue(ok)
        self.assertEqual(len(res["added"]), 2)
        ok, res = todo_list(s)
        self.assertTrue(ok)
        self.assertEqual(res["total"], 2)
        self.assertFalse(res["auto"])
        ok, res = todo_pop(s)
        self.assertTrue(ok)
        self.assertEqual([i["text"] for i in res["popped"]], ["a"])
        self.assertEqual(res["pending"], 1)

    def test_peek_done_remove_clear(self) -> None:
        s = StubSession()
        todo_append(s, texts=["a", "b", "c"])
        ok, res = todo_peek(s, count=2)
        self.assertTrue(ok)
        self.assertEqual(len(res["selection"]), 2)
        self.assertEqual(len(res["items"]), 3)  # full list untouched
        self.assertEqual(res["pending"], 3)
        ok, res = todo_done(s, ids=1)
        self.assertTrue(ok)
        self.assertEqual(res["pending"], 2)
        ok, res = todo_remove(s, ids=2)
        self.assertTrue(ok)
        self.assertEqual(res["removed"], 1)
        ok, res = todo_clear(s)
        self.assertTrue(ok)
        self.assertEqual(res["cleared"], 1)
        # clear keeps done items unless include_done=True.
        self.assertEqual(len(load_todo_items(s)), 1)
        ok, res = todo_clear(s, include_done=True)
        self.assertTrue(ok)
        self.assertEqual(load_todo_items(s), [])

    def test_state_survives_across_tool_calls(self) -> None:
        s = StubSession()
        todo_append(s, text="x")
        # A fresh read sees what the previous tool recorded.
        self.assertEqual(len(load_todo_items(s)), 1)

    def test_recorded_history_converges(self) -> None:
        # Rapid successive tools each record on the anchor; the stored
        # truth contains every action in order.
        s = StubSession()
        todo_append(s, text="a")
        todo_append(s, text="b")
        todo_pop(s)
        stored = load_todo_items(s)  # must unwrap the [True, payload] envelope
        self.assertEqual([i["text"] for i in stored], ["a", "b"])
        self.assertEqual(stored[0]["status"], "done")
        self.assertEqual(load_todo_items(s), stored)

    def test_list_peek_do_not_record(self) -> None:
        # Read-only actions must not append history: a recorded prediction
        # could otherwise shadow newer state (latest record wins).
        s = StubSession()
        todo_append(s, text="a")
        recorded = len(s.anchor.history)
        todo_list(s)
        todo_peek(s)
        self.assertEqual(len(s.anchor.history), recorded)
        self.assertEqual(len(load_todo_items(s)), 1)

    def test_command_controls_auto(self) -> None:
        s = StubSession()
        self.assertFalse(is_todo_auto(s))
        res = todo_command(s, action="auto-on")
        self.assertTrue(res["auto"])
        self.assertTrue(is_todo_auto(s))
        res = todo_command(s, action="auto-off")
        self.assertFalse(res["auto"])
        res = todo_command(s, action="bogus")
        self.assertEqual(res["status"], "error")
        res = todo_command(s, action="clear")
        self.assertEqual(res["status"], "success")

    def test_set_todo_auto_helper(self) -> None:
        s = StubSession()
        set_todo_auto(s, True)
        self.assertTrue(is_todo_auto(s))


if __name__ == "__main__":
    unittest.main()
