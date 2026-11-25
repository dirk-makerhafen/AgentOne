"""Tests for provider/key status and recent query error-rate summaries."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.provider_enums import HealthStatus
from server.models.providers.ai_model_offering import AiModelOffering as AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class ProviderStatusSummaryTest(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="status-provider")
        self.key = ApiKey.objects.create(api_provider=self.provider, key="k1")
        self.other_key = ApiKey.objects.create(api_provider=self.provider, key="k2")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="Status Model", provider_model_id="status-model"
        )

        agent = AgentModel.objects.create(name="status-agent")
        version = AgentVersionModel.objects.create(
            agent=agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = SessionModel.objects.create(name="status-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=agent, pinned_agent_version=version
        )

    def _response(self, key, status, error_type="", error_message=""):
        query = Query.objects.create(
            session=self.session,
            session_version=self.sv,
            apikey=key,
            status=(
                QueryStatus.SUCCESS if status == ResponseStatus.SUCCESS else QueryStatus.FAILURE
            ),
        )
        return Response.objects.create(
            query=query,
            session=self.session,
            session_version=self.sv,
            status=status,
            aimodel=self.model,
            error_type=error_type,
            error_message=error_message,
        )

    def test_recent_error_stats_ignores_in_flight_responses(self):
        self._response(self.key, ResponseStatus.SUCCESS)
        self._response(self.key, ResponseStatus.FAILURE, "rate_limit", "provider_rate_limit")
        self._response(self.key, ResponseStatus.FAILURE, "server", "cache corruption")
        self._response(self.key, ResponseStatus.ACTIVE)

        stats = self.provider.recent_query_error_stats(limit=100)
        self.assertEqual(stats["sample_size"], 3)
        self.assertEqual(stats["failures"], 2)
        self.assertEqual(stats["rate_limited"], 1)
        self.assertEqual(stats["error_rate"], 66.7)
        self.assertEqual(stats["error_types"], [{"type": "server", "count": 1}])

        # The limit applies to the most recently created completed rows.
        limited = self.key.recent_query_error_stats(limit=2)
        self.assertEqual(limited["sample_size"], 2)
        self.assertEqual(limited["failures"], 2)
        self.assertEqual(limited["error_rate"], 100.0)

    def test_error_stats_are_scoped_to_one_key(self):
        self._response(self.key, ResponseStatus.FAILURE, "server", "boom")
        self._response(self.other_key, ResponseStatus.SUCCESS)

        self.assertEqual(self.key.recent_query_error_stats()["error_rate"], 100.0)
        self.assertEqual(self.other_key.recent_query_error_stats()["error_rate"], 0.0)
        self.assertEqual(self.provider.recent_query_error_stats(apikey=self.other_key)["sample_size"], 1)

    def test_status_summary_shows_active_key_cooldown(self):
        self.key.record_provider_cooldown(120, reason="rate limited")
        self.key.refresh_from_db()
        self.other_key.enabled = False
        self.other_key.save(update_fields=["enabled"])

        summary = self.provider.status_summary()
        self.assertTrue(summary["rate_limited"])
        self.assertIn("cooldown_until", summary["rate_limit_reason"])
        self.assertEqual(summary["status"], HealthStatus.UNKNOWN)
        # Only enabled keys are listed; a healthy sibling would keep the
        # provider usable even while this key is parked.
        self.assertEqual(len(summary["keys"]), 1)

        key_summary = next(row for row in summary["keys"] if row["id"] == self.key.pk)
        self.assertEqual(key_summary["status"], HealthStatus.RATE_LIMITED)
        self.assertTrue(key_summary["rate_limited"])
        self.assertEqual(key_summary["rate_limit_hits"], 1)
        self.assertIsNotNone(key_summary["cooldown_until"])

    def test_expired_cooldown_is_not_reported_as_limited(self):
        self.key.status = HealthStatus.RATE_LIMITED
        self.key.rate_limit_until = timezone.now() - timedelta(seconds=1)
        self.key.save()

        summary = self.key.status_summary()
        self.assertFalse(summary["rate_limited"])
        self.assertEqual(summary["status_label"], "Rate limited (cooldown elapsed)")
