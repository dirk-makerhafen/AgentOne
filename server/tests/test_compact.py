"""Tests for context compaction — history_limiter, compact, build_llm_context."""
from __future__ import annotations

from django.test import TestCase

from runtime.session.session import Session
from server.models.message import Message, MessagePart
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.settings import SettingsModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.history_limiter import (
    estimate_message_tokens,
    find_compaction_boundary,
)
from server.models.content import IMAGE_TOKEN_ESTIMATE


def _runtime(sv):
    session = Session(session_model=sv.session)
    return session


def _link(messages):
    """Chain ``prev_message`` links oldest -> newest."""
    prev = None
    for m in messages:
        Message.objects.filter(pk=m.pk).update(prev_message=prev)
        prev = m


class FindCompactionBoundaryTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            # Production-like history window: the boundary finder mirrors
            # build_llm_context's max_history_messages + 1 walk, so a bare
            # (0/None) window would only ever see the newest message and no
            # boundary could exist.
            agent_settings=SettingsModel.objects.create(max_history_messages=100),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)
        self.session.refresh_from_db()
        self.runtime = _runtime(self.sv)

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

    def _run(self, auto_compact_keep_percent=15):
        SettingsModel.objects.filter(pk=self.av.agent_settings.pk).update(
            auto_compact_keep_percent=auto_compact_keep_percent
        )
        self.runtime.agent.get_version_model()
        self.av.refresh_from_db()
        self.runtime = _runtime(self.sv)
        return self.runtime

    def test_boundary_is_newest_message_to_compact(self):
        msgs = [self._create_message(text=f"m{i}") for i in range(10)]
        _link(msgs)
        boundary = find_compaction_boundary(self.runtime, self.runtime.get_last_message())
        # 10 equal ~9-token messages; keep 15% -> keeps the 2 newest, compacts
        # the 8 oldest.  Boundary = the 8th (m7).
        self.assertIsNotNone(boundary)
        self.assertEqual(boundary.pk, msgs[7].pk)

    def test_no_boundary_when_all_fits_in_keep_budget(self):
        self._run(auto_compact_keep_percent=100)
        msgs = [self._create_message(text=f"m{i}") for i in range(4)]
        _link(msgs)
        boundary = find_compaction_boundary(self.runtime, self.runtime.get_last_message())
        self.assertIsNone(boundary)

    def test_zero_keep_percent_compacts_everything(self):
        self._run(auto_compact_keep_percent=0)
        msgs = [self._create_message(text=f"m{i}") for i in range(5)]
        _link(msgs)
        boundary = find_compaction_boundary(self.runtime, self.runtime.get_last_message())
        # Explicit 0 keeps nothing: the boundary is the newest message itself.
        self.assertIsNotNone(boundary)
        self.assertEqual(boundary.pk, msgs[-1].pk)

    def test_walk_stops_at_compaction_marker(self):
        a = self._create_message(text="a")
        b = self._create_message(text="b")
        b2 = self._create_message(text="b2")
        c = self._create_message(text="c")
        _link([a, b])
        marker = self._create_compaction_message(text="old summary")
        Message.objects.filter(pk=marker.pk).update(prev_message=b)
        _link([b2, c])
        # Chain: a -> b -> marker -> b2 -> c  (marker lies between b and b2)
        Message.objects.filter(pk=b2.pk).update(prev_message=marker)
        boundary = find_compaction_boundary(self.runtime, self.runtime.get_last_message())
        # Walk stops at the marker; only [marker, b2, c] are considered.
        self.assertIsNotNone(boundary)
        self.assertIn(boundary.pk, (marker.pk, b2.pk, c.pk))

    def test_assistant_toolcall_newest_compacted_is_kept(self):
        a = self._create_message(text="a")
        b = self._create_message(text="b")
        c = self._create_message(role=MessageRole.ASSISTANT, text="c")
        d = self._create_message(text="d")
        _link([a, b, c, d])
        # Give c a TOOLCALL part so it must not be the newest compacted.
        MessagePart.objects.create(
            message=c,
            type=MessagePartType.TOOLCALL,
            content=GenericContent.from_data({"name": "some_tool"}),
            content_type=MessageContentType.JSON,
        )
        boundary = find_compaction_boundary(self.runtime, self.runtime.get_last_message())
        self.assertIsNotNone(boundary)
        # The boundary moves older than c (c is kept, so the newest to compact is b).
        self.assertEqual(boundary.pk, b.pk)


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

    def _message(self, role=MessageRole.USER, text="hello"):
        msg = Message.objects.create(session=self.sv.session, session_version=self.sv, role=role)
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=GenericContent.from_text(text),
            content_type=MessageContentType.TEXT,
        )
        return msg

    def test_estimate_is_positive(self):
        self.assertGreater(estimate_message_tokens(self._message(text="hello")), 0)

    def test_estimate_scales_with_length(self):
        short = estimate_message_tokens(self._message(text="short"))
        long = estimate_message_tokens(self._message(text="l" * 4000))
        self.assertGreater(long, short)

    def test_estimate_returns_zero_for_none(self):
        self.assertEqual(estimate_message_tokens(None), 0)

    def test_estimate_image_is_fixed_not_base64_proportional(self):
        uri = "data:image/jpeg;base64," + "A" * 2_000_000  # ~500k raw chars
        msg = Message.objects.create(session=self.sv.session, session_version=self.sv, role=MessageRole.USER)
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=GenericContent.from_image(uri),
            content_type=MessageContentType.IMAGE,
        )
        # A raw-string estimate would be ~526k tokens; the fixed image estimate
        # must be far smaller (fixed per-image billing, not per base64 char).
        self.assertLess(estimate_message_tokens(msg), 5000)
        self.assertGreater(estimate_message_tokens(msg), IMAGE_TOKEN_ESTIMATE)


class FindTurnBoundaryTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            # See FindCompactionBoundaryTest: the walk needs a real window.
            agent_settings=SettingsModel.objects.create(max_history_messages=100),
        )
        self.session = SessionModel.objects.create(name="test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)
        self.session.refresh_from_db()
        self.runtime = _runtime(self.sv)

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

    def _toolcall(self, msg: Message) -> None:
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.TOOLCALL,
            content=GenericContent.from_data({"name": "some_tool"}),
            content_type=MessageContentType.JSON,
        )

    def test_boundary_never_splits_assistant_toolcall(self):
        a = self._msg(MessageRole.USER, "a")
        b = self._msg(MessageRole.ASSISTANT, "b")
        self._toolcall(b)
        c = self._msg(MessageRole.TOOL, "c")  # tool result follows the toolcall
        # Keep budget tiny so only the assistant toolcall (b) would otherwise be
        # the newest compacted — the guard must keep b too, making the boundary
        # a.
        settings = self.av.agent_settings
        Message.objects.filter(pk=a.pk).update(prev_message=None)
        Message.objects.filter(pk=b.pk).update(prev_message=a)
        Message.objects.filter(pk=c.pk).update(prev_message=b)
        SettingsModel.objects.filter(pk=settings.pk).update(auto_compact_keep_percent=5)
        self.av.refresh_from_db()
        the_runtime = _runtime(self.sv)
        boundary = find_compaction_boundary(the_runtime, the_runtime.get_last_message())
        self.assertEqual(boundary.pk, a.pk)
