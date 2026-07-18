"""Tests for context compaction — history_limiter, compact, build_llm_context."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase

from server.models.message import Message, MessagePart
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.settings import SettingsModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider
from server.history_limiter import (
    HistoryLimiter,
    find_compaction_boundary,
    estimate_message_tokens,
    estimate_tokens_from_text,
)
from server.tests.helpers import AgentMdTestMixin


class FindCompactionBoundaryTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )

    def _create_message(self, role: str = "user", text: str = "hello") -> Message:
        msg = Message.objects.create(
            session_version=self.sv,
            role=role,
        )
        content = GenericContent.from_text(text)
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=content,
            content_type=MessageContentType.TEXT,
        )
        return msg

    def _create_compaction_message(self, text: str = "summary") -> Message:
        msg = Message.objects.create(
            session_version=self.sv,
            role="system",
        )
        content = GenericContent.from_text(text)
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.COMPACTION,
            content=content,
            content_type=MessageContentType.TEXT,
        )
        return msg

    def test_no_boundary_returns_zero(self):
        msg = self._create_message()
        pk = find_compaction_boundary(self.session.get_runtime(), msg.pk)
        self.assertEqual(pk, 0)

    def test_boundary_found(self):
        compact = self._create_compaction_message("earlier summary")
        user = self._create_message()
        pk = find_compaction_boundary(self.session.get_runtime(), user.pk)
        self.assertEqual(pk, compact.pk)

    def test_boundary_filters_by_pk_lte(self):
        compact = self._create_compaction_message("summary")
        _later = self._create_message()
        pk = find_compaction_boundary(self.session.get_runtime(), compact.pk - 1)
        self.assertEqual(pk, 0)

    def test_multiple_boundaries_last_is_returned(self):
        _first = self._create_compaction_message("first")
        _second = self._create_compaction_message("second")
        _user = self._create_message()
        pk = find_compaction_boundary(self.session.get_runtime(), _user.pk)
        self.assertEqual(pk, _second.pk)

    def test_returns_most_recent_by_created_at(self):
        compact_later = self._create_compaction_message("later")
        _user = self._create_message()
        compact_later.created_at = _user.created_at
        compact_later.save()
        pk = find_compaction_boundary(self.session.get_runtime(), _user.pk)
        self.assertEqual(pk, compact_later.pk)


class EstimateMessageTokensTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )

    def test_estimates_text_message(self):
        msg = Message.objects.create(
            session_version=self.sv,
            role="user",
        )
        content = GenericContent.from_text("hello world")
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=content,
            content_type=MessageContentType.TEXT,
        )
        tokens = estimate_message_tokens(msg)
        self.assertGreater(tokens, 0)

    def test_empty_message_returns_role_overhead(self):
        msg = Message.objects.create(
            session_version=self.sv,
            role="user",
        )
        tokens = estimate_message_tokens(msg)
        self.assertGreater(tokens, 0)

    def test_role_overhead_is_positive(self):
        user = Message.objects.create(
            session_version=self.sv,
            role="user",
        )
        assistant = Message.objects.create(
            session_version=self.sv,
            role="assistant",
        )
        user_tokens = estimate_message_tokens(user)
        assistant_tokens = estimate_message_tokens(assistant)
        self.assertGreater(user_tokens, 0)
        self.assertGreater(assistant_tokens, 0)


class EstimateTokensFromTextTest(TestCase):
    def test_basic_text(self):
        tokens = estimate_tokens_from_text("hello world")
        self.assertEqual(tokens, 2)

    def test_empty_string(self):
        tokens = estimate_tokens_from_text("")
        self.assertEqual(tokens, 0)

    def test_longer_text(self):
        tokens = estimate_tokens_from_text("this is a longer text with several words")
        self.assertGreater(tokens, 5)


class FindTurnBoundaryTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )

    def _msg(self, role: str, text: str) -> Message:
        msg = Message.objects.create(
            session_version=self.sv,
            role=role,
        )
        content = GenericContent.from_text(text)
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=content,
            content_type=MessageContentType.TEXT,
        )
        return msg

    def test_cut_at_exact_limit(self):
        messages = [
            self._msg("user", "a"),
            self._msg("assistant", "b"),
            self._msg("user", "c"),
        ]
        index = HistoryLimiter.find_turn_boundary(messages, 1000000)
        self.assertEqual(index, 0)

    def test_cut_rounds_to_assistant(self):
        messages = [
            self._msg("assistant", "ok"),
            self._msg("user", "hi"),
            self._msg("assistant", "x" * 1200),
            self._msg("user", "x" * 1200),
        ]
        index = HistoryLimiter.find_turn_boundary(messages, 400)
        self.assertEqual(index, 0)

    def test_no_cut_when_all_within_budget(self):
        messages = [
            self._msg("user", "a"),
            self._msg("assistant", "b"),
        ]
        index = HistoryLimiter.find_turn_boundary(messages, 1000000)
        self.assertEqual(index, 0)



