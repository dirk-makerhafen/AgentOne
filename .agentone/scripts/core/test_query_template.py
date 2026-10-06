import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

from query_template import (  # noqa: E402
    template_delete,
    template_execute,
    template_get,
    template_list,
    template_render,
    template_save,
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
    def __init__(self, pk, task=None):
        self.model = _Model(pk)
        self._task = task or _Task()

    def get_task(self, name):
        assert name == "call_llm_direct"
        return self._task


class _TempSessions:
    """Redirect the sessions base at runtime.session_folder.

    ``session_dir`` / ``session_templates_dir`` / ``ensure_*`` all resolve
    the base via ``get_sessions_base()`` at call time, so patching that
    single function redirects every helper (including the copies already
    imported into ``runtime.query_templates``).
    """

    def __init__(self, td):
        self.td = td

    def __enter__(self):
        import runtime.session_folder as sf

        self._patch = patch.object(
            sf, "get_sessions_base", return_value=Path(self.td)
        )
        self._patch.start()
        return self

    def __exit__(self, *args):
        self._patch.stop()


class TestTemplateTools(unittest.TestCase):
    def test_save_list_get_render_delete(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                s = _Session(11)
                ok, res = template_save(
                    s, name="summarize", body="Points {{ max_points }}: {{ text }}",
                    description="d",
                    variables=[{"name": "text"}, {"name": "max_points",
                               "type": "integer", "default": 5}],
                )
                self.assertTrue(ok, res)

                ok, res = template_list(s)
                self.assertTrue(ok)
                self.assertEqual(len(res["templates"]), 1)

                ok, res = template_get(s, name="summarize")
                self.assertTrue(ok)
                self.assertIn("text", res["template"]["body"])

                ok, res = template_render(s, name="summarize", variables={"text": "hi"})
                self.assertTrue(ok, res)
                self.assertIn("5", res["rendered"])

                ok, res = template_render(s, name="summarize", variables={})
                self.assertFalse(ok)
                self.assertIn("text", res["message"])

                ok, res = template_delete(s, name="summarize")
                self.assertTrue(ok)
                ok, res = template_list(s)
                self.assertEqual(res["templates"], [])

    def test_save_requires_body(self):
        ok, res = template_save(_Session(1), name="x", body="  ")
        self.assertFalse(ok)

    def test_save_rejects_bare_string_variables(self):
        # Regression: "question" must not become 8 one-character variables.
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                s = _Session(11)
                ok, res = template_save(
                    s, name="t", body="Q: {{ question }}", variables="question",
                )
                self.assertFalse(ok)
                self.assertIn("[{'name': 'question'}]", res["message"])

    def test_save_accepts_json_string_variables(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                s = _Session(11)
                ok, res = template_save(
                    s, name="t", body="Q: {{ question }}",
                    variables='[{"name": "question"}]',
                )
                self.assertTrue(ok, res)
                self.assertEqual(
                    [v["name"] for v in res["template"]["variables"]],
                    ["question"],
                )

    def test_render_accepts_json_string_values(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                s = _Session(11)
                template_save(
                    s, name="t", body="Q: {{ question }}",
                    variables=[{"name": "question"}],
                )
                ok, res = template_render(
                    s, name="t", variables='{"question": "why?"}',
                )
                self.assertTrue(ok, res)
                self.assertIn("why?", res["rendered"])

    def test_get_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                ok, res = template_get(_Session(1), name="nope")
                self.assertFalse(ok)

    def test_execute_dispatches_rendered(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                task = _Task()
                s = _Session(7, task=task)
                template_save(s, name="t", body="Hi {{ who }}",
                              variables=[{"name": "who"}])
                out = template_execute(s, name="t", variables={"who": "bob"},
                                       model="m")
                self.assertEqual(out[0], "dispatched")
                sent = task.calls[0]
                self.assertEqual(sent["messages"],
                                 [{"role": "user", "content": "Hi bob"}])
                self.assertEqual(sent["model_name"], "m")

    def test_execute_missing_var_fails_fast(self):
        with tempfile.TemporaryDirectory() as td:
            with _TempSessions(td):
                task = _Task()
                s = _Session(7, task=task)
                template_save(s, name="t", body="Hi {{ who }}",
                              variables=[{"name": "who"}])
                ok, res = template_execute(s, name="t", variables={})
                self.assertFalse(ok)
                self.assertIn("who", res["error"])
                self.assertEqual(task.calls, [])

    def test_execute_no_session(self):
        ok, res = template_execute(None, name="t", variables={})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
