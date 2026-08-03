"""Tests for context compaction — history_limiter, compact, build_llm_context."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase

from server.models.message import Message, MessagePart
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.settings import SettingsModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider
from server.history_limiter import (
    HistoryLimiter,
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

    def _create_message(self, role: str = MessageRole.USER, text: str = "hello") -> Message:
        msg = Message.objects.create(
            session=self.sv.session,
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
            session=self.sv.session,
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
            session=self.sv.session,
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
