import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

import workflow as tools_module  # noqa: E402
import workflow_tasks as tasks_module  # noqa: E402
from runtime.session_workflows import WorkflowError  # noqa: E402
from workflow import (  # noqa: E402
    workflow_create,
    workflow_delete,
    workflow_get,
    workflow_list,
    workflow_run,
    workflow_update,
    workflow_validate,
)


class _Model:
    def __init__(self, pk):
        self.pk = pk


class _Task:
    def __init__(self):
        self.calls = []

    def delay(self, **kwargs):
        self.calls.append(kwargs)
        return ("dispatched", kwargs)


class _Session:
    def __init__(self, pk, tools=None, tasks=None):
        self.model = _Model(pk)
        self._tools = tools or {}
        self._tasks = tasks or {}

    def get_tool(self, name):
        return self._tools.get(name)

    def get_task(self, name):
        return self._tasks.get(name)


def _steps():
    return [{"id": "fetch", "tool": "echo", "args": {"text": "hi"}}]


class TestWorkflowTools(unittest.TestCase):
    def test_list_returns_engine_result(self):
        with patch("runtime.session_workflows.list_workflows",
                   return_value=[{"name": "w"}]) as mock_list:
            ok, res = workflow_list(_Session(11))
        self.assertTrue(ok)
        self.assertEqual(res["workflows"], [{"name": "w"}])
        mock_list.assert_called_once_with(11)

    def test_list_engine_error(self):
        with patch("runtime.session_workflows.list_workflows",
                   side_effect=Exception("db down")):
            ok, res = workflow_list(_Session(11))
        self.assertFalse(ok)
        self.assertIn("db down", res["message"])

    def test_get_returns_definition(self):
        with patch("runtime.session_workflows.get_workflow",
                   return_value={"name": "w", "definition": {}, "meta": {}}):
            ok, res = workflow_get(_Session(1), name="w")
        self.assertTrue(ok)
        self.assertIn("definition", res)

    def test_get_missing(self):
        with patch("runtime.session_workflows.get_workflow",
                   side_effect=WorkflowError("No workflow named 'nope'.")):
            ok, res = workflow_get(_Session(1), name="nope")
        self.assertFalse(ok)
        self.assertIn("nope", res["message"])

    def test_create_passes_values_through(self):
        with patch("runtime.session_workflows.create_workflow",
                   return_value={"name": "w", "version": 3,
                                 "steps": 1}) as mock_create, \
                patch("workflow._policy", return_value="POLICY"):
            ok, res = workflow_create(
                _Session(11), name="w", steps=_steps(), description="d",
                inputs_schema={"type": "object"},
            )
        self.assertTrue(ok, res)
        mock_create.assert_called_once_with(11, "w", _steps(), "d",
                                            {"type": "object"},
                                            policy="POLICY")
        self.assertEqual(res["version"], 3)

    def test_create_engine_error(self):
        with patch("runtime.session_workflows.create_workflow",
                   side_effect=WorkflowError("Workflow 'w' already exists.")):
            ok, res = workflow_create(_Session(1), name="w", steps=_steps())
        self.assertFalse(ok)
        self.assertIn("already exists", res["message"])

    def test_update_passes_values_through(self):
        with patch("runtime.session_workflows.update_workflow",
                   return_value={"name": "w", "version": 4,
                                 "steps": 2}) as mock_update, \
                patch("workflow._policy", return_value="POLICY"):
            ok, res = workflow_update(_Session(11), name="w", steps=_steps())
        self.assertTrue(ok, res)
        mock_update.assert_called_once_with(11, "w", _steps(), None, None,
                                            policy="POLICY")

    def test_update_unchanged(self):
        with patch("runtime.session_workflows.update_workflow",
                   return_value={"name": "w", "version": 4, "unchanged": True}):
            ok, res = workflow_update(_Session(1), name="w", steps=_steps())
        self.assertTrue(ok)
        self.assertTrue(res["unchanged"])

    def test_delete_ok(self):
        with patch("runtime.session_workflows.delete_workflow",
                   return_value={"name": "w"}) as mock_delete:
            ok, res = workflow_delete(_Session(1), name="w")
        self.assertTrue(ok)
        self.assertEqual(res["name"], "w")
        mock_delete.assert_called_once_with(1, "w")

    def test_validate_ok(self):
        with patch("runtime.session_workflows.validate_workflow",
                   return_value={"name": "w", "description": "",
                                 "inputs_schema": {}, "steps": _steps()}):
            ok, res = workflow_validate(_Session(1), steps=_steps())
        self.assertTrue(ok)
        self.assertEqual(res["steps"], 1)

    def test_validate_error(self):
        with patch("runtime.session_workflows.validate_workflow",
                   side_effect=WorkflowError("duplicate step id 'a'")):
            ok, res = workflow_validate(_Session(1), steps=[])
        self.assertFalse(ok)
        self.assertIn("duplicate", res["message"])

    def test_run_returns_dispatched_call(self):
        sentinel = MagicMock()
        session = _Session(7)
        with patch("runtime.session_workflows.run_workflow",
                   return_value=sentinel) as mock_run:
            out = workflow_run(session, name="w", inputs={"t": "x"})
        self.assertIs(out, sentinel)
        mock_run.assert_called_once_with(session, "w", {"t": "x"},
                                         _visited=None)

    def test_run_engine_error_tuple(self):
        with patch("runtime.session_workflows.run_workflow",
                   return_value=(False, {"status": "error", "message": "nope"})):
            out = workflow_run(_Session(1), name="nope")
        self.assertEqual(out, (False, {"status": "error", "message": "nope"}))

    def test_run_unexpected_exception(self):
        with patch("runtime.session_workflows.run_workflow",
                   side_effect=Exception("boom")):
            ok, res = workflow_run(_Session(1), name="w")
        self.assertFalse(ok)
        self.assertIn("boom", res["message"])


class TestWorkflowTaskWrappers(unittest.TestCase):
    def test_step_forwards(self):
        with patch("runtime.session_workflows.step_workflow",
                   return_value="next") as mock_step:
            out = tasks_module.workflow_step(_Session(1), {"a": 1}, 0)
        self.assertEqual(out, "next")
        mock_step.assert_called_once()

    def test_advance_forwards(self):
        with patch("runtime.session_workflows.advance_workflow",
                   return_value="next"):
            out = tasks_module.workflow_advance(_Session(1), {}, 0, {"v": 1})
        self.assertEqual(out, "next")

    def test_join_forwards(self):
        with patch("runtime.session_workflows.join_workflow",
                   return_value="next"):
            out = tasks_module.workflow_join(_Session(1), {}, 0, [{"v": 1}])
        self.assertEqual(out, "next")

    def test_fanout_forwards(self):
        with patch("runtime.session_workflows.fanout_workflow",
                   return_value="next"):
            out = tasks_module.workflow_fanout(_Session(1), {}, 0, [1, 2])
        self.assertEqual(out, "next")

    def test_mapjoin_forwards(self):
        with patch("runtime.session_workflows.mapjoin_workflow",
                   return_value="next"):
            out = tasks_module.workflow_mapjoin(_Session(1), {}, 0, [], [], [])
        self.assertEqual(out, "next")

    def test_inline_forwards_to_isolated_runner(self):
        with patch("runtime.adhoc_tools.run_inline_function",
                   return_value=(True, {"result": 1})) as mock_run:
            out = tasks_module.workflow_inline(
                _Session(1), "return 1", {"a": 1})
        self.assertEqual(out, (True, {"result": 1}))
        mock_run.assert_called_once()
        _session, source, params = mock_run.call_args[0]
        self.assertEqual(source, "return 1")
        self.assertEqual(params, {"a": 1})


if __name__ == "__main__":
    unittest.main()
