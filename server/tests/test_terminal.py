"""Tests for persistent named terminals (model + libtmux manager + allowlist)."""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from runtime.terminal.allowlist import (
    first_token,
    is_external_cli_allowed,
    unapproved_agent_cli,
)
from runtime.terminal.manager import slugify, tmux_name_for
from server.models.sessions.session import SessionModel
from server.models.terminal import TerminalSession, TerminalStatus


class AllowlistTest(SimpleTestCase):
    def test_first_token(self) -> None:
        self.assertEqual(first_token("claude -p 'hi'"), "claude")
        self.assertEqual(first_token("/usr/local/bin/hermes run"), "hermes")
        self.assertEqual(first_token(""), "")

    def test_allowlisted_binaries_pass(self) -> None:
        self.assertTrue(is_external_cli_allowed("claude"))
        self.assertTrue(is_external_cli_allowed("hermes --version"))
        self.assertEqual(unapproved_agent_cli("claude -p 'hi'"), "")

    def test_ordinary_binaries_are_not_gated(self) -> None:
        # Shell builtins, dev tools, and unknown binaries are covered by
        # the content/path guardrails only — the recognition gate stays
        # silent so normal shell use never halts.
        self.assertEqual(unapproved_agent_cli("ls -la"), "")
        self.assertEqual(unapproved_agent_cli("eviltool --run"), "")
        self.assertEqual(unapproved_agent_cli(""), "")

    def test_unapproved_agent_cli_is_recognized(self) -> None:
        # Simulate an org that removed claude from the allowlist: the
        # recognized binary is flagged no matter which tool invoked it.
        with mock.patch(
            "runtime.terminal.allowlist.allowed_binaries",
            return_value={"hermes", "git"},
        ):
            self.assertEqual(unapproved_agent_cli("claude -p 'hi'"), "claude")
            self.assertEqual(unapproved_agent_cli("hermes --version"), "")
            self.assertEqual(unapproved_agent_cli("ls"), "")


class SlugTest(SimpleTestCase):
    def test_slugify(self) -> None:
        self.assertEqual(slugify("Dev Env!"), "dev-env")
        self.assertEqual(slugify(""), "default")

    def test_tmux_name(self) -> None:
        self.assertEqual(tmux_name_for(12, "dev"), "agentone-s12-dev")


class FakePane:
    def __init__(self, lines=None):
        self.lines = list(lines or ["$ "])
        self.sent = []

    def capture_pane(self):
        return list(self.lines)

    def send_keys(self, text, enter=True):
        self.sent.append((text, enter))

    def pipe_pane(self, _cmd):
        return None


class FakeWindow:
    def __init__(self, pane):
        self.active_pane = pane


class FakeTmuxSession:
    def __init__(self, name, pane=None):
        self._name = name
        self.pane = pane or FakePane()
        self.active_window = FakeWindow(self.pane)
        self.killed = False

    def get(self, key):
        if key == "session_name":
            return self._name
        raise KeyError(key)

    def kill_session(self):
        self.killed = True


class FakeServer:
    def __init__(self):
        self.sessions: dict[str, FakeTmuxSession] = {}

    def find_where(self, where):
        return self.sessions.get(where.get("session_name"))

    def new_session(self, session_name, start_directory=None, attach=False, **_kw):
        session = FakeTmuxSession(session_name)
        self.sessions[session_name] = session
        return session

    def list_sessions(self):
        return list(self.sessions.values())


class TerminalManagerTest(TestCase):
    def setUp(self):
        self.session = SessionModel.objects.create(name="term-session")

    def test_ensure_creates_row_and_tmux_session(self) -> None:
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            row = mgr.ensure_terminal(self.session_model(), name="dev", cwd="/tmp")
        self.assertEqual(row.name, "dev")
        self.assertEqual(row.status, TerminalStatus.RUNNING)
        self.assertIn(row.tmux_session_name, server.sessions)

    def test_ensure_is_idempotent(self) -> None:
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            first = mgr.ensure_terminal(self.session_model(), name="dev", cwd="/tmp")
            second = mgr.ensure_terminal(self.session_model(), name="dev", cwd="/tmp")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(len(server.sessions), 1)

    def test_exec_waits_for_sentinel(self) -> None:
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            row = mgr.ensure_terminal(self.session_model(), name="default", cwd="/tmp")
            pane = server.sessions[row.tmux_session_name].pane
            seen = {"n": 0}
            real_capture = pane.capture_pane

            def _capture():
                seen["n"] += 1
                base = real_capture()
                if seen["n"] >= 2:
                    return base + ["output line", "__AGENTONE_DONE_abc=0"]
                return base

            with mock.patch.object(pane, "capture_pane", side_effect=lambda: _capture()):
                with mock.patch.object(mgr.uuid, "uuid4", return_value=mock.Mock(hex="abc")):
                    result = mgr.exec_command(
                        self.session_model(), "echo hi", name="default", timeout=5
                    )
        self.assertEqual(result["return_code"], 0)
        self.assertIn("output line", result["stdout"])

    def test_kill_marks_dead(self) -> None:
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            mgr.ensure_terminal(self.session_model(), name="dev", cwd="/tmp")
            result = mgr.kill_terminal(self.session_model(), name="dev")
        self.assertEqual(result["status"], "success")
        row = TerminalSession.objects.get(session=self.session, name="dev")
        self.assertEqual(row.status, TerminalStatus.DEAD)

    def test_reap_idle_kills_stale(self) -> None:
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            mgr.ensure_terminal(self.session_model(), name="old", cwd="/tmp")
        TerminalSession.objects.filter(session=self.session, name="old").update(
            last_active_at=timezone.now() - timedelta(hours=5)
        )
        with mock.patch.object(mgr, "_server", return_value=server):
            count = mgr.reap_idle_terminals(max_idle_seconds=3600)
        self.assertEqual(count, 1)
        row = TerminalSession.objects.get(session=self.session, name="old")
        self.assertEqual(row.status, TerminalStatus.DEAD)

    def test_terminal_source_arg_extraction(self) -> None:
        from runtime.tasks.call_scheduler import CallScheduler

        tc = mock.Mock()
        tc.carguments_json = {"command": "echo hi"}
        self.assertEqual(CallScheduler._terminal_source_arg(tc), "echo hi")
        tc.carguments_json = {"text": "y"}
        self.assertEqual(CallScheduler._terminal_source_arg(tc), "y")

    def session_model(self) -> SessionModel:
        return SessionModel.objects.get(pk=self.session.pk)
