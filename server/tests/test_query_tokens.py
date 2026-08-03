"""Regression tests for Query / QueryMessage token accounting.

Covers the recalibration bug in ``Response.save``: a SUCCESS response must set
``query.tokens`` to the authoritative backend-reported ``prompt_tokens``, and
must scale message-level estimates (which include dynamically-rendered tool
results) rather than part-level estimates (which do not contain tool results).
"""
from __future__ import annotations

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import MessageContentType, MessageRole
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class QueryTokenRecalibrationTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="token-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="token-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()

    def _make_query(self):
        query = Query.objects.create(
            session = self.sv.session,
            session_version=self.sv
        )
        query.add_message(
            role=MessageRole.SYSTEM,
            content_type=MessageContentType.TEXT,
            content="system prompt",
        )
        query.add_message(
            role=MessageRole.USER,
            content_type=MessageContentType.TEXT,
            content="hello world",
        )
        return query

    def test_success_sets_query_tokens_to_backend_prompt_tokens(self):
        """On SUCCESS, query.tokens must be the authoritative backend count."""
        query = self._make_query()
        query.tokens = 1000  # rough pre-call estimate
        query.save()

        response = Response.objects.create(
            query=query,
            session = self.sv.session,
            session_version=self.sv,
            status=ResponseStatus.SUCCESS,
            prompt_tokens=90000,
            completion_tokens=100,
        )
        response.save()

        query.refresh_from_db()
        self.assertEqual(query.tokens, 90000)

    def test_message_tokens_scaled_instead_of_zeroed(self):
        """Message-level estimates are scaled proportionally; the old code
        rebuilt query.tokens from part tokens and dropped dynamically-rendered
        tool-result tokens (collapsing ~74k → ~6k and zeroing tool messages)."""
        query = self._make_query()
        # Simulate build-time estimate including tool results.
        qm = QueryMessage.objects.filter(query=query).first()
        qm.tokens = 5000
        qm.save()
        query.tokens = 5000
        query.save()

        response = Response.objects.create(
            query=query,
            session = self.sv.session,
            session_version=self.sv,
            status=ResponseStatus.SUCCESS,
            prompt_tokens=10000,  # factor 2.0
            completion_tokens=10,
        )
        response.save()

        qm.refresh_from_db()
        query.refresh_from_db()
        self.assertEqual(query.tokens, 10000)
        self.assertEqual(qm.tokens, 10000)  # 5000 * 2.0

    def test_no_calibration_when_actual_matches_estimate(self):
        """Correction factor within 1% → no token rewrite."""
        query = self._make_query()
        query.tokens = 10000
        query.save()

        response = Response.objects.create(
            query=query,
            session = self.sv.session,
            session_version=self.sv,
            status=ResponseStatus.SUCCESS,
            prompt_tokens=10050,  # factor 1.005 → within tolerance
            completion_tokens=10,
        )
        response.save()

        query.refresh_from_db()
        self.assertEqual(query.tokens, 10000)

    def test_non_success_response_does_not_recalibrate(self):
        """FAILURE responses must not touch query.tokens."""
        query = self._make_query()
        query.tokens = 1000
        query.save()

        Response.objects.create(
            query=query,
            session = self.sv.session,
            session_version=self.sv,
            status=ResponseStatus.FAILURE,
            prompt_tokens=90000,
            completion_tokens=10,
        ).save()

        query.refresh_from_db()
        self.assertEqual(query.tokens, 1000)
