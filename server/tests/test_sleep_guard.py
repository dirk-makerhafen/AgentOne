"""Tests for the worker-independent sleep guard (runtime/sleep_guard.py).

Pure decision logic (``desired_state``) is exercised with mocks; the
DB-backed recent-activity query uses Django ``TestCase``; ``manage_sleep_guard``
reconciliation is tested with everything below subprocess-level replaced.
"""
from __future__ import annotations

import tempfile
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from runtime import sleep_guard
from runtime.sleep_guard import desired_state

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class DesiredStateTest(TestCase):
    def test_non_darwin_disabled(self):
        with mock.patch("runtime.sleep_guard.sys.platform", "linux"):
            on, reason = desired_state(True)
        self.assertFalse(on)
        self.assertEqual(reason, "not macOS")

    def test_preference_disabled(self):
        with mock.patch("runtime.sleep_guard.sys.platform", "darwin"):
            with mock.patch("runtime.sleep_guard.get_prevent_sleep_when_local_ai", return_value=False):
                on, _ = desired_state(True)
        self.assertFalse(on)

    def test_low_battery_disabled(self):
        with mock.patch("runtime.sleep_guard.sys.platform", "darwin"):
            with mock.patch("runtime.sleep_guard.get_prevent_sleep_when_local_ai", return_value=True):
                with mock.patch("runtime.sleep_guard.caffeinate_allowed", return_value=False):
                    on, reason = desired_state(True)
        self.assertFalse(on)
        self.assertEqual(reason, "battery too low")

    def test_no_recent_activity_disabled(self):
        with mock.patch("runtime.sleep_guard.sys.platform", "darwin"):
            with mock.patch("runtime.sleep_guard.get_prevent_sleep_when_local_ai", return_value=True):
                with mock.patch("runtime.sleep_guard.caffeinate_allowed", return_value=True):
                    on, reason = desired_state(False)
        self.assertFalse(on)
        self.assertEqual(reason, "no recent local activity")

    def test_all_green_enabled(self):
        with mock.patch("runtime.sleep_guard.sys.platform", "darwin"):
            with mock.patch("runtime.sleep_guard.get_prevent_sleep_when_local_ai", return_value=True):
                with mock.patch("runtime.sleep_guard.caffeinate_allowed", return_value=True):
                    on, reason = desired_state(True)
        self.assertTrue(on)
        self.assertEqual(reason, "local activity in grace window")


class RecentLocalActivityTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="test-provider")
        self.aimodel_local = AiModel.objects.create(
            api_provider=self.provider,
            name="local",
            self_hosted=True,
            is_cloud=False,
        )
        self.aimodel_cloud = AiModel.objects.create(
            api_provider=self.provider,
            name="cloud",
            self_hosted=False,
            is_cloud=True,
        )
        self.agent = AgentModel.objects.create(name="sg-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="sg-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()

    def _response(self, aimodel, created_dt):
        return Response.objects.create(
            query=None,
            session=self.session,
            session_version=self.sv,
            status="SUCCESS",
            aimodel=aimodel,
            created_at=created_dt,
            updated_at=created_dt,
        )

    def test_grace_zero_disables(self):
        with mock.patch("runtime.sleep_guard.get_sleep_guard_release_delay_minutes", return_value=0):
            self.assertFalse(sleep_guard.has_recent_local_activity())

    def test_fresh_local_response_counts(self):
        self._response(self.aimodel_local, timezone.now())
        with mock.patch("runtime.sleep_guard.get_sleep_guard_release_delay_minutes", return_value=5):
            self.assertTrue(sleep_guard.has_recent_local_activity())

    def test_old_local_response_ignored(self):
        old = timezone.now() - timedelta(minutes=30)
        resp = self._response(self.aimodel_local, old)
        Response.objects.filter(pk=resp.pk).update(created_at=old)
        with mock.patch("runtime.sleep_guard.get_sleep_guard_release_delay_minutes", return_value=5):
            self.assertFalse(sleep_guard.has_recent_local_activity())

    def test_cloud_only_response_ignored(self):
        self._response(self.aimodel_cloud, timezone.now())
        with mock.patch("runtime.sleep_guard.get_sleep_guard_release_delay_minutes", return_value=5):
            self.assertFalse(sleep_guard.has_recent_local_activity())

    def test_no_responses_ignored(self):
        with mock.patch("runtime.sleep_guard.get_sleep_guard_release_delay_minutes", return_value=5):
            self.assertFalse(sleep_guard.has_recent_local_activity())


class ManageSleepGuardTest(TestCase):
    """Reconciliation — everything below the manager is mocked."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pidfile = Path(self._tmp.name) / "sleep_guard.pid"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *, has_recent, active, overrides=None):
        opts = {
            "spawn_ok": True,
            "allowed": True,
            "enabled": True,
            "darwin": True,
        }
        if overrides:
            opts.update(overrides)
        with ExitStack() as stack:
            stack.enter_context(mock.patch("runtime.sleep_guard.PID_FILE", self.pidfile))
            stack.enter_context(mock.patch("runtime.sleep_guard.sys.platform", "darwin" if opts["darwin"] else "linux"))
            stack.enter_context(mock.patch("runtime.sleep_guard.get_prevent_sleep_when_local_ai", return_value=opts["enabled"]))
            stack.enter_context(mock.patch("runtime.sleep_guard.caffeinate_allowed", return_value=opts["allowed"]))
            spawn = stack.enter_context(mock.patch("runtime.sleep_guard._spawn_caffeinate", return_value=opts["spawn_ok"]))
            stop = stack.enter_context(mock.patch("runtime.sleep_guard._stop_caffeinate", return_value=True))
            stack.enter_context(mock.patch("runtime.sleep_guard.has_recent_local_activity", return_value=has_recent))
            stack.enter_context(mock.patch("runtime.sleep_guard.guard_is_active", return_value=active))
            result = sleep_guard.manage_sleep_guard()
        return result, spawn, stop

    def test_starts_when_activity_and_off(self):
        result, spawn, stop = self._run(has_recent=True, active=False)
        self.assertEqual(result["state"], "started")
        spawn.assert_called_once()
        stop.assert_not_called()

    def test_start_failure_reported(self):
        result, _, _ = self._run(has_recent=True, active=False, overrides={"spawn_ok": False})
        self.assertEqual(result["state"], "start_failed")

    def test_stays_running_when_activity_and_on(self):
        result, spawn, stop = self._run(has_recent=True, active=True)
        self.assertEqual(result["state"], "running")
        spawn.assert_not_called()
        stop.assert_not_called()

    def test_stops_when_no_activity(self):
        result, spawn, stop = self._run(has_recent=False, active=True)
        self.assertEqual(result["state"], "stopped")
        stop.assert_called_once()
        spawn.assert_not_called()

    def test_off_when_neither_activity_nor_on(self):
        result, spawn, stop = self._run(has_recent=False, active=False)
        self.assertEqual(result["state"], "off")
        spawn.assert_not_called()
        stop.assert_not_called()

    def test_low_battery_never_starts(self):
        result, spawn, _ = self._run(has_recent=True, active=False, overrides={"allowed": False})
        self.assertEqual(result["state"], "off")
        self.assertEqual(result["reason"], "battery too low")
        spawn.assert_not_called()

    def test_non_darwin_never_starts(self):
        result, spawn, _ = self._run(has_recent=True, active=False, overrides={"darwin": False})
        self.assertEqual(result["state"], "off")
        spawn.assert_not_called()