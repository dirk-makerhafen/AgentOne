import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

import query_template as tools_module  # noqa: E402
from query_template import (  # noqa: E402
    template_delete,
    template_execute,
    template_get,
    template_list,
    template_render,
    template_save,
)
from runtime.query_templates import TemplateError  # noqa: E402


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
    def __init__(self, pk, task=None):
        self.model = _Model(pk)
        self._task = task or _Task()

    def get_task(self, name):
        assert name == "call_llm_direct"
        return self._task


def _fake_template(**kwargs):
    kwargs.setdefault("name", "t")
    template = MagicMock()
    template.name = kwargs["name"]
    template.to_dict = lambda include_body=True: {
        "name": kwargs["name"],
        "description": "",
        "variables": [{"name": "question", "type": "string", "required": True}],
        **({"body": "Q: {{ question }}"} if include_body else {}),
    }
    return template


class TestTemplateTools(unittest.TestCase):
    def test_list_returns_engine_result(self):
        with patch.object(
            tools_module, "list_templates", return_value=[{"name": "t"}]
        ) as mock_list:
            ok, res = template_list(_Session(11))
        self.assertTrue(ok)
        self.assertEqual(res["templates"], [{"name": "t"}])
        mock_list.assert_called_once_with(11)

    def test_list_engine_error(self):
        with patch.object(
            tools_module, "list_templates", side_effect=Exception("db down")
        ):
            ok, res = template_list(_Session(11))
        self.assertFalse(ok)
        self.assertIn("db down", res["message"])

    def test_get_returns_template_with_body(self):
        with patch.object(
            tools_module, "get_template", return_value=_fake_template()
        ):
            ok, res = template_get(_Session(1), name="t")
        self.assertTrue(ok)
        self.assertIn("body", res["template"])

    def test_get_missing(self):
        with patch.object(
            tools_module, "get_template", side_effect=TemplateError("not found")
        ):
            ok, res = template_get(_Session(1), name="nope")
        self.assertFalse(ok)
        self.assertIn("not found", res["message"])

    def test_get_requires_name(self):
        ok, res = template_get(_Session(1), name="  ")
        self.assertFalse(ok)

    def test_save_passes_values_and_source_through(self):
        with patch.object(
            tools_module, "save_template", return_value=_fake_template()
        ) as mock_save:
            ok, res = template_save(
                _Session(11), name="t", body="Q: {{ question }}",
                description="d", variables=[{"name": "question"}],
            )
        self.assertTrue(ok, res)
        mock_save.assert_called_once_with(
            11, "t", "Q: {{ question }}", description="d",
            variables=[{"name": "question"}], source="tool",
        )
        self.assertEqual(res["template"]["name"], "t")

    def test_save_requires_body(self):
        ok, res = template_save(_Session(1), name="x", body="  ")
        self.assertFalse(ok)

    def test_save_engine_error(self):
        with patch.object(
            tools_module, "save_template",
            side_effect=TemplateError("Missing required variable(s): question"),
        ):
            ok, res = template_save(
                _Session(1), name="t", body="Q: {{ question }}",
                variables="question",
            )
        self.assertFalse(ok)
        self.assertIn("question", res["message"])

    def test_delete_ok(self):
        with patch.object(tools_module, "delete_template") as mock_delete:
            ok, res = template_delete(_Session(1), name="t")
        self.assertTrue(ok)
        self.assertEqual(res["name"], "t")
        mock_delete.assert_called_once_with(1, "t")

    def test_render_ok(self):
        with patch.object(
            tools_module, "render_template_by_name",
            return_value=(_fake_template(), "Q: why?"),
        ):
            ok, res = template_render(
                _Session(1), name="t", variables={"question": "why?"},
            )
        self.assertTrue(ok, res)
        self.assertEqual(res["rendered"], "Q: why?")

    def test_render_error(self):
        with patch.object(
            tools_module, "render_template_by_name",
            side_effect=TemplateError("Missing required variable(s): question"),
        ):
            ok, res = template_render(_Session(1), name="t", variables={})
        self.assertFalse(ok)
        self.assertIn("question", res["message"])

    def test_execute_dispatches_rendered(self):
        with patch.object(
            tools_module, "render_template_by_name",
            return_value=(_fake_template(), "Hi bob"),
        ):
            task = _Task()
            s = _Session(7, task=task)
            out = template_execute(s, name="t", variables={"who": "bob"}, model="m")
        self.assertEqual(out[0], "dispatched")
        sent = task.calls[0]
        self.assertEqual(sent["messages"], [{"role": "user", "content": "Hi bob"}])
        self.assertEqual(sent["model_name"], "m")

    def test_execute_render_error_fails_fast(self):
        with patch.object(
            tools_module, "render_template_by_name",
            side_effect=TemplateError("Missing required variable(s): who"),
        ):
            task = _Task()
            s = _Session(7, task=task)
            ok, res = template_execute(s, name="t", variables={})
        self.assertFalse(ok)
        self.assertIn("who", res["error"])
        self.assertEqual(task.calls, [])

    def test_execute_no_task_available(self):
        with patch.object(
            tools_module, "render_template_by_name",
            return_value=(_fake_template(), "Hi"),
        ):
            s = _Session(7, task=None)
            s.get_task = lambda name: None
            ok, res = template_execute(s, name="t", variables={})
        self.assertFalse(ok)
        self.assertIn("call_llm_direct", res["error"])

    def test_execute_no_session(self):
        ok, res = template_execute(None, name="t", variables={})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
