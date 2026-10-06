from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.test import TestCase

from runtime.query_templates import delete_template, save_template
from server.models import SessionModel
from ui.app import UiApp
from ui.main.rightpanel.session.rightpanel_session_templates import (
    RightPanelSessionTemplates,
)


class MockParent:
    """Minimal parent stand-in providing what ModelView needs."""

    def __init__(self):
        self._instance = MagicMock()
        self._instance.add_css_string = MagicMock()

    def _add_child(self, child):
        pass


class TemplatesPanelTest(TestCase):
    def setUp(self):
        self.ui_app = UiApp()
        self.session_model = SessionModel.objects.create(name="tpl_session")
        self.parent = MockParent()
        self.panel = RightPanelSessionTemplates(
            subject=self.session_model, parent=self.parent
        )
        save_template(
            self.session_model.pk,
            "summarize",
            "Points {{ max_points }}: {{ text }}",
            description="Summarizer",
            variables=[
                {"name": "text", "type": "string", "required": True},
                {"name": "max_points", "type": "integer", "default": 5},
            ],
            source="panel",
        )

    def tearDown(self):
        UiApp._instance = None

    def _mock_session(self, task=None):
        session = MagicMock()
        session.model.pk = self.session_model.pk
        session.get_task = MagicMock(return_value=task)
        self.panel.session = session
        return session

    def test_templates_listed(self):
        names = [t["name"] for t in self.panel.templates]
        self.assertEqual(names, ["summarize"])

    def test_empty_folder_lists_nothing(self):
        other = SessionModel.objects.create(name="tpl_empty")
        panel = RightPanelSessionTemplates(subject=other, parent=self.parent)
        self.assertEqual(panel.templates, [])

    def test_select_initializes_defaults(self):
        self.panel.selectTemplate("summarize")
        self.assertEqual(self.panel._selected, "summarize")
        self.assertEqual(self.panel._values, {"text": "", "max_points": "5"})
        self.assertEqual(self.panel._error, "")

    def test_select_missing_shows_error(self):
        self.panel.selectTemplate("nope")
        self.assertIn("not found", self.panel._error)

    def test_preview_renders_with_values(self):
        self.panel.selectTemplate("summarize")
        self.panel.setVar("text", "hi")
        self.panel.previewTemplate()
        self.assertIn("5", self.panel._preview)
        self.assertIn("hi", self.panel._preview)
        self.assertEqual(self.panel._error, "")

    def test_preview_missing_required_shows_error(self):
        self.panel.selectTemplate("summarize")
        self.panel.previewTemplate()
        self.assertIn("text", self.panel._error)
        self.assertEqual(self.panel._preview, "")

    def test_run_dispatches_rendered_prompt(self):
        task = MagicMock()
        task.delay = MagicMock(return_value=SimpleNamespace(pk=77))
        self._mock_session(task=task)
        self.panel.selectTemplate("summarize")
        self.panel.setVar("text", "hello")
        self.panel.runTemplate()
        self.assertEqual(self.panel._run_call_pk, 77)
        self.assertEqual(self.panel._run_status, "running")
        task.delay.assert_called_once()
        sent = task.delay.call_args
        self.assertEqual(
            sent.kwargs["messages"],
            [{"role": "user", "content": "Points 5: hello"}],
        )

    def test_run_render_error_fails_fast(self):
        task = MagicMock()
        self._mock_session(task=task)
        self.panel.selectTemplate("summarize")
        self.panel.runTemplate()  # text missing
        self.assertIn("text", self.panel._error)
        task.delay.assert_not_called()
        self.assertIsNone(self.panel._run_call_pk)

    def test_run_without_task_shows_error(self):
        self._mock_session(task=None)
        self.panel.selectTemplate("summarize")
        self.panel.setVar("text", "hi")
        self.panel.runTemplate()
        self.assertIn("call_llm_direct", self.panel._error)

    def test_orm_event_completes_run(self):
        task = MagicMock()
        task.delay = MagicMock(return_value=SimpleNamespace(pk=77))
        self._mock_session(task=task)
        self.panel.selectTemplate("summarize")
        self.panel.setVar("text", "hi")
        self.panel.runTemplate()
        fake_call = MagicMock()
        fake_call.get_result = MagicMock(return_value={
            "content": "done!",
            "status": "SUCCESS",
            "model": "m",
        })
        with patch(
            "server.models.tasks.agent_task_call.AgentTaskCall"
        ) as mock_call_model:
            mock_call_model.objects.get = MagicMock(return_value=fake_call)
            self.panel._on_orm_event(
                model="AgentTaskCall", pk=77, action="update", data={}
            )
        self.assertEqual(self.panel._result, "done!")
        self.assertEqual(self.panel._run_status, "done")

    def test_orm_event_ignores_other_calls(self):
        self.panel._run_call_pk = 77
        self.panel._run_status = "running"
        self.panel._on_orm_event(model="AgentTaskCall", pk=78, action="update")
        self.assertEqual(self.panel._run_status, "running")
        self.assertEqual(self.panel._result, "")

    def test_orm_event_no_result_recorded(self):
        self.panel._run_call_pk = 77
        self.panel._run_status = "running"
        fake_call = MagicMock()
        fake_call.get_result = MagicMock(return_value=None)
        with patch(
            "server.models.tasks.agent_task_call.AgentTaskCall"
        ) as mock_call_model:
            mock_call_model.objects.get = MagicMock(return_value=fake_call)
            self.panel._on_orm_event(
                model="AgentTaskCall", pk=77, action="update", data={}
            )
        self.assertEqual(self.panel._run_status, "ended")
        self.assertIn("no result", self.panel._run_meta)

    def test_orm_event_result_error_stays_visible(self):
        self.panel._run_call_pk = 77
        self.panel._run_status = "running"
        fake_call = MagicMock()
        fake_call.get_result = MagicMock(side_effect=RuntimeError("db gone"))
        with patch(
            "server.models.tasks.agent_task_call.AgentTaskCall"
        ) as mock_call_model:
            mock_call_model.objects.get = MagicMock(return_value=fake_call)
            self.panel._on_orm_event(
                model="AgentTaskCall", pk=77, action="update", data={}
            )
        self.assertEqual(self.panel._run_status, "ended")
        self.assertIn("db gone", self.panel._result)

    def test_orm_event_pending_stays_running(self):
        self.panel._run_call_pk = 77
        self.panel._run_status = "running"
        fake_call = MagicMock()
        fake_call.get_result = MagicMock(side_effect=TimeoutError("not ready"))
        fake_call.status_detail = "ACTIVE_RUNNING"
        with patch(
            "server.models.tasks.agent_task_call.AgentTaskCall"
        ) as mock_call_model:
            mock_call_model.objects.get = MagicMock(return_value=fake_call)
            self.panel._on_orm_event(
                model="AgentTaskCall", pk=77, action="update", data={}
            )
        self.assertTrue(self.panel._run_status.startswith("running"))
        self.assertEqual(self.panel._result, "")

    def test_delete_template(self):
        self.panel.selectTemplate("summarize")
        self.panel.deleteTemplate("summarize")
        self.assertEqual(self.panel.templates, [])
        self.assertIsNone(self.panel._selected)

    def test_refresh_clears_deleted_selection(self):
        self.panel.selectTemplate("summarize")
        delete_template(self.session_model.pk, "summarize")
        self.panel.refreshTemplates()
        self.assertIsNone(self.panel._selected)
        self.assertIsNone(self.panel.selected_template)

    def test_clear_run(self):
        self.panel._run_call_pk = 77
        self.panel._run_status = "running"
        self.panel.clearRun()
        self.assertIsNone(self.panel._run_call_pk)
        self.assertEqual(self.panel._run_status, "")
