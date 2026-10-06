"""Tests for the session right-panel Terminals tab (read-only viewer)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from server.models.sessions.session import SessionModel
from server.models.terminal import TerminalSession, TerminalStatus
from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
from ui.main.rightpanel.session.rightpanel_session_terminal import (
    RightPanelSessionTerminals,
)


class FakeParent:
    _instance = None

    def _add_child(self, _child) -> None:
        return None


class TerminalTabTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="ui-term-session")
        self.view = RightPanelSessionTerminals(self.session, FakeParent())

    def _row(self, name="dev", **kwargs):
        defaults = {
            "session": self.session,
            "name": name,
            "tmux_session_name": f"agentone-s{self.session.pk}-{name}",
            "status": TerminalStatus.RUNNING,
            "cwd": "/tmp",
        }
        defaults.update(kwargs)
        return TerminalSession.objects.create(**defaults)

    def test_terminals_lists_manager_rows(self) -> None:
        self._row("dev")
        rows = [
            {"name": "dev", "status": "running", "tmux": "x", "alive": True,
             "cwd": "/tmp", "last_active_at": None},
            {"name": "agent", "status": "running", "tmux": "y", "alive": False,
             "cwd": "/tmp", "last_active_at": None},
        ]
        with mock.patch(
            "runtime.terminal.manager.list_terminals", return_value=rows
        ):
            self.assertEqual([t["name"] for t in self.view.terminals], ["agent", "dev"])

    def test_terminals_falls_back_to_db_without_tmux(self) -> None:
        self._row("dev")
        with mock.patch(
            "runtime.terminal.manager.list_terminals",
            side_effect=RuntimeError("tmux binary not found"),
        ):
            terminals = self.view.terminals
        self.assertEqual([t["name"] for t in terminals], ["dev"])
        self.assertFalse(terminals[0]["alive"])

    def test_empty_state(self) -> None:
        with mock.patch(
            "runtime.terminal.manager.list_terminals",
            side_effect=RuntimeError("no tmux"),
        ):
            self.assertEqual(self.view.terminals, [])

    def test_select_and_kill(self) -> None:
        self._row("dev")
        self.view.select("dev")
        self.assertEqual(self.view.selected_name, "dev")
        with mock.patch(
            "runtime.terminal.manager.kill_terminal",
            return_value={"status": "success"},
        ) as kill:
            self.view.kill("dev")
            kill.assert_called_once_with(self.session, name="dev")
        self.assertIsNone(self.view.selected_name)

    def test_kill_falls_back_to_dead_row(self) -> None:
        row = self._row("dev")
        with mock.patch(
            "runtime.terminal.manager.kill_terminal",
            side_effect=RuntimeError("no tmux"),
        ):
            self.view.kill("dev")
        row.refresh_from_db()
        self.assertEqual(row.status, TerminalStatus.DEAD)

    def test_selected_output_escapes_html(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as tmp:
            tmp.write("line one\n<script>alert(1)</script>\n")
            log_path = tmp.name
        try:
            self._row("dev", log_path=log_path)
            self.view.select("dev")
            output = self.view.selected_output
            self.assertIn("line one", output)
            self.assertNotIn("<script>", output)
            self.assertIn("&lt;script&gt;", output)
        finally:
            Path(log_path).unlink(missing_ok=True)

    def test_selected_output_empty_without_log(self) -> None:
        self._row("dev")
        self.view.select("dev")
        with mock.patch(
            "runtime.terminal.manager.poll_output",
            side_effect=RuntimeError("no tmux"),
        ):
            self.assertEqual(self.view.selected_output, "(no output captured yet)")

    def test_switch_tab_wiring(self) -> None:
        panel = RightPanelSession(self.session, FakeParent())
        panel.switchTab("terminal")
        self.assertEqual(panel.current_tab_name, "terminal")
        self.assertIsInstance(panel.current_tab, RightPanelSessionTerminals)
