"""Tests for the model smoke-test runner."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model_offering import AiModelOffering as AiModel
from server.models.sessions.session import SessionModel


class BestUsableModelTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p1")
        self.m_bad = AiModel.objects.create(
            api_provider=self.provider, name="Bad", provider_model_id="bad",
            status="UNAVAILABLE", enabled=True,
        )
        self.m_good = AiModel.objects.create(
            api_provider=self.provider, name="Good", provider_model_id="good",
            status="HEALTHY", enabled=True,
        )
        self.m_disabled = AiModel.objects.create(
            api_provider=self.provider, name="Disabled", provider_model_id="disabled",
            enabled=False,
        )

    def test_skips_unavailable_and_disabled(self):
        from runtime.test_run import best_usable_model
        picked = best_usable_model(self.provider.pk)
        self.assertEqual(picked.pk, self.m_good.pk)

    def test_falls_back_when_all_unavailable(self):
        self.m_good.status = "UNAVAILABLE"
        self.m_good.save(update_fields=["status"])
        from runtime.test_run import best_usable_model
        picked = best_usable_model(self.provider.pk)
        # Falls back to the (only) candidate rather than None.
        self.assertIsNotNone(picked)

    def test_none_when_no_models(self):
        from runtime.test_run import best_usable_model
        p2 = ApiProvider.objects.create(name="empty")
        self.assertIsNone(best_usable_model(p2.pk))


class RetentionTest(TestCase):
    def test_purge_keeps_newest_n(self):
        for i in range(25):
            SessionModel.objects.create(
                name=f"[test] x {i}",
                session_type="test",
                turn_count=0,
                unattended_turn_count=0,
                is_active=False,
                last_active_at=timezone.now(),
            )
        from runtime.test_run import _purge_old_test_sessions
        deleted = _purge_old_test_sessions(20)
        self.assertEqual(deleted, 5)
        remaining = SessionModel.objects.filter(session_type="test").count()
        self.assertEqual(remaining, 20)


class SmokeTestVerdictTest(TestCase):
    """Regression: the wait loop must not reference nonexistent enum members.

    ``TaskCallStatus`` has no ``FAILED``/``CANCELLED``/``RATE_LIMITED`` members
    (those live in ``status_detail``), so the old loop raised
    ``AttributeError`` on its first iteration and reported every model as
    failed.
    """

    class _FakeCall:
        pk = 1
        status = None
        status_detail = None

        class objects:  # noqa: N801 - mimics the model manager
            @staticmethod
            def get(**kwargs):
                return SmokeTestVerdictTest._FakeCall()

        def get_result(self, timeout=0):
            return None

    def setUp(self):
        from server.models.enums.task_enums import (
            TaskCallStatus,
            TaskCallStatusDetail,
        )

        self.provider = ApiProvider.objects.create(name="verdict-provider")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Verdict", provider_model_id="verdict",
            enabled=True,
        )
        self._FakeCall.status = TaskCallStatus.ENDED
        self._FakeCall.status_detail = TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION

    def test_ended_failure_reports_failed_without_attribute_error(self):
        from runtime.test_run import run_model_test

        session_mock = MagicMock()
        session_mock.add_user_message.return_value = self._FakeCall()
        sv = MagicMock()
        sv.session.pk = 1
        agent_version = MagicMock()
        agent_version.get_or_create_session.return_value = sv

        agent = MagicMock()
        agent.latest_agent_version = agent_version

        with patch("runtime.test_run._pick_test_agent", return_value=agent), \
             patch("runtime.test_run.Session", return_value=session_mock):
            result = run_model_test(self.model.pk, timeout=1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "failed")
        self.assertEqual(result["error_kind"], "exception")
        overrides = agent_version.get_or_create_session.call_args.kwargs["settings_overrides"]
        self.assertEqual(overrides["reasoning_effort"], "low")


class ProbeTaskTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="p2")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="M", provider_model_id="m", enabled=True,
        )

    def test_probe_model_caches_and_publishes(self):
        fake_result = {
            "ok": True, "verdict": "healthy", "answer": "yes",
            "model": "M", "provider": "p2", "model_pk": self.model.pk,
            "session_pk": 42, "latency_ms": 10, "tokens": {"prompt": 1, "completion": 1},
            "error_kind": None, "error_message": "", "tested_at": "x",
        }
        with patch("server.tasks.probe_model.run_model_test", return_value=fake_result) as m:
            with patch("server.models.providers.ai_model_offering.AiModelOffering.publish_by_pk") as pub:
                from server.tasks.probe_model import probe_model
                out = probe_model(self.model.pk)
                self.assertEqual(out["verdict"], "healthy")
                m.assert_called_once_with(self.model.pk)
                pub.assert_called_once()
        from server.tasks.probe_model import get_cached_result, is_running
        cached = get_cached_result(self.model.pk)
        self.assertEqual(cached["verdict"], "healthy")
        self.assertFalse(is_running(self.model.pk))

    def test_probe_model_handles_exception(self):
        with patch("server.tasks.probe_model.run_model_test", side_effect=RuntimeError("boom")):
            from server.tasks.probe_model import probe_model
            out = probe_model(self.model.pk)
            self.assertEqual(out["verdict"], "failed")
            self.assertIn("boom", out["error_message"])
        from server.tasks.probe_model import get_cached_result
        self.assertEqual(get_cached_result(self.model.pk)["verdict"], "failed")
