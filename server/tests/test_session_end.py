"""Tests for the ``session_end`` task and ``Session.request_end``.

Session deactivation is the single ``session_end`` task path (the anchor for
``session_end`` intercept hooks); ``set_is_active`` is a hookless low-level
setter. See ``docs/session-hooks.md`` §5.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from django.test import TestCase

from server.tests.helpers import AgentMdTestMixin


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_session_end():
    """Load ``.agentone/scripts/core/session_end.py`` as a module."""
    path = _REPO_ROOT / ".agentone" / "scripts" / "core" / "session_end.py"
    spec = importlib.util.spec_from_file_location("_session_end_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.session_end


class SessionEndTaskTest(AgentMdTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_task_deactivates_and_returns_frame(self):
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        result = _load_session_end()(runtime, reason="unit")
        self.assertTrue(result["transitioned"])
        self.assertEqual(result["reason"], "unit")
        self.assertIn("session_type", result)
        self.assertIn("last_message_pk", result)
        session.refresh_from_db()
        self.assertFalse(session.is_active)

    def test_request_end_dispatches_task(self):
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        task = MagicMock()
        runtime.get_task = MagicMock(return_value=task)
        runtime.request_end(reason="dispatched")
        task.delay.assert_called_once_with(reason="dispatched")
        # The task (not request_end) performs the deactivation.
        session.refresh_from_db()
        self.assertTrue(session.is_active)

    def test_request_end_falls_back_without_task(self):
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        runtime.get_task = MagicMock(return_value=None)
        runtime.request_end()
        session.refresh_from_db()
        self.assertFalse(session.is_active)

    def test_set_is_active_is_hookless(self):
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        runtime.set_is_active(False)
        session.refresh_from_db()
        self.assertFalse(session.is_active)
