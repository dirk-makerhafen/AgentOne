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
        self.piped = []

    def capture_pane(self):
        return list(self.lines)

    def send_keys(self, text, enter=True):
        self.sent.append((text, enter))

    def cmd(self, subcommand, *args, **kwargs):
        self.piped.append((subcommand, args))
        return None


class FakeWindow:
    def __init__(self, pane):
        self.active_pane = pane


class FakeTmuxSession:
    def __init__(self, name, pane=None):
        self.session_name = name
        self.pane = pane or FakePane()
        self.active_window = FakeWindow(self.pane)
        self.killed = False

    def kill(self):
        self.killed = True


class FakeSessionList:
    """Mirrors the libtmux ``Server.sessions`` query surface we rely on."""

    def __init__(self, store):
        self._store = store

    def get(self, session_name=None, default=None, **_kwargs):
        return self._store.get(session_name, default)

    def __iter__(self):
        return iter(list(self._store.values()))

    def __len__(self):
        return len(self._store)

    def __contains__(self, name):
        return name in self._store


class FakeServer:
    def __init__(self):
        self._sessions: dict[str, FakeTmuxSession] = {}

    @property
    def sessions(self):
        return FakeSessionList(self._sessions)

    def new_session(self, session_name, start_directory=None, attach=False, **_kw):
        session = FakeTmuxSession(session_name)
        self._sessions[session_name] = session
        return session


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
            pane = server.sessions.get(session_name=row.tmux_session_name).pane
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

    def test_exec_recreates_missing_tmux_session(self) -> None:
        """The reported live failure: row is RUNNING but tmux has no such
        session (externally killed). exec must recreate transparently
        instead of raising 'Terminal died — re-run'."""
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            row = mgr.ensure_terminal(self.session_model(), name="default", cwd="/tmp")
            # Simulate an externally killed tmux session: row says RUNNING,
            # tmux knows nothing about it.
            del server._sessions[row.tmux_session_name]
            pane_holder: dict = {}

            real_new_session = server.new_session

            def _new_session(*args, **kwargs):
                session = real_new_session(*args, **kwargs)
                pane_holder["pane"] = session.pane
                seen = {"n": 0}
                real_capture = session.pane.capture_pane

                def _capture():
                    seen["n"] += 1
                    base = real_capture()
                    if seen["n"] >= 2:
                        return base + ["recreated output", "__AGENTONE_DONE_abc=0"]
                    return base

                session.pane.capture_pane = _capture  # type: ignore[method-assign]
                return session

            with mock.patch.object(server, "new_session", side_effect=_new_session):
                with mock.patch.object(mgr.uuid, "uuid4", return_value=mock.Mock(hex="abc")):
                    result = mgr.exec_command(
                        self.session_model(), "ls", name="default", timeout=5
                    )
        self.assertEqual(result["return_code"], 0)
        self.assertIn("recreated output", result["stdout"])
        row.refresh_from_db()
        self.assertEqual(row.status, TerminalStatus.RUNNING)

    def test_exec_reports_shell_exit_fast(self) -> None:
        """Commands that kill their own shell (`exit`, `exec`) fail fast
        with ``shell_exited`` instead of polling until timeout, and the
        row is marked dead so the next call recreates it."""
        import time

        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            row = mgr.ensure_terminal(self.session_model(), name="default", cwd="/tmp")
            pane = server.sessions.get(session_name=row.tmux_session_name).pane
            real_find = mgr._find_tmux_session
            calls = {"n": 0}

            def _flaky_find(tmux_server, name):
                calls["n"] += 1
                if calls["n"] >= 3:
                    return None  # shell died mid-command
                return real_find(tmux_server, name)

            with mock.patch.object(mgr, "_find_tmux_session", side_effect=_flaky_find):
                with mock.patch.object(pane, "capture_pane", return_value=["partial"]):
                    started = time.time()
                    result = mgr.exec_command(
                        self.session_model(), "exit 3", name="default", timeout=30
                    )
                    elapsed = time.time() - started
        self.assertTrue(result.get("shell_exited"))
        self.assertEqual(result["return_code"], -1)
        self.assertLess(elapsed, 10)
        row.refresh_from_db()
        self.assertEqual(row.status, TerminalStatus.DEAD)

    def test_pipe_pane_uses_pane_cmd(self) -> None:
        """Log setup must use the current ``Pane.cmd('pipe-pane', …)`` API."""
        from runtime.terminal import manager as mgr

        server = FakeServer()
        with mock.patch.object(mgr, "_server", return_value=server):
            row = mgr.ensure_terminal(self.session_model(), name="dev", cwd="/tmp")
        pane = server.sessions.get(session_name=row.tmux_session_name).pane
        self.assertTrue(
            any(call[0] == "pipe-pane" for call in pane.piped),
            f"expected a pipe-pane call, got: {pane.piped}",
        )

    def test_api_surface_check_rejects_old_libtmux(self) -> None:
        """A libtmux without ``Server.sessions.get`` fails fast with a clear
        error instead of degrading into misleading 'terminal died'."""
        from types import SimpleNamespace

        from runtime.terminal import manager as mgr

        with self.assertRaises(RuntimeError) as ctx:
            mgr._check_libtmux_api(SimpleNamespace())
        self.assertIn("libtmux", str(ctx.exception))

    def test_terminal_source_arg_extraction(self) -> None:
        from runtime.tasks.call_scheduler import CallScheduler

        tc = mock.Mock()
        tc.carguments_json = {"command": "echo hi"}
        self.assertEqual(CallScheduler._terminal_source_arg(tc), "echo hi")
        tc.carguments_json = {"text": "y"}
        self.assertEqual(CallScheduler._terminal_source_arg(tc), "y")

    def session_model(self) -> SessionModel:
        return SessionModel.objects.get(pk=self.session.pk)
