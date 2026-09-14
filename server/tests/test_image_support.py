"""Image support: IMAGE parts, image_url serialization, tool image results, vision gating."""
from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase

from runtime.session.session import Session

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent, IMAGE_TOKEN_ESTIMATE
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message, MessagePart
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.queries.query import Query
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.history_limiter import estimate_message_tokens

_URI = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="


def _make_session() -> tuple[Session, SessionVersionModel]:
    agent = AgentModel.objects.create(name="img-agent")
    av = AgentVersionModel.objects.create(
        agent=agent,
        agent_settings=SettingsModel.objects.create(),
    )
    session = SessionModel.objects.create(name="img-session")
    sv = SessionVersionModel.objects.create(
        session=session,
        agent=agent,
        pinned_agent_version=av,
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    session.refresh_from_db()
    return Session(session_model=session), sv


class ImagePartStorageTest(TestCase):
    def test_add_part_image_is_deduplicated(self):
        _, sv = _make_session()
        msg = Message.objects.create(role=MessageRole.USER, session=sv.session, session_version=sv)
        part = msg.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.IMAGE, content=_URI
        )
        msg2 = Message.objects.create(role=MessageRole.USER, session=sv.session, session_version=sv)
        part2 = msg2.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.IMAGE, content=_URI
        )
        self.assertEqual(part.content_type, MessageContentType.IMAGE)
        self.assertEqual(part.content.sha256, part2.content.sha256)
        self.assertEqual(GenericContent.objects.count(), 1)


class ImageSerializationTest(TestCase):
    def setUp(self):
        self.session, self.sv = _make_session()
        self.query = self._query()

    def _query(self) -> Query:
        return Query.objects.create(session=self.sv.session, session_version=self.sv)

    def _build_query_message(self, msg: Message):
        self.query.add_message(role=msg.role, source_message=msg)

    def test_chat_image_part_becomes_image_url_block(self):
        msg = Message.objects.create(role=MessageRole.USER, session=self.sv.session, session_version=self.sv)
        msg.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT,
            content="what is in this photo?",
        )
        msg.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.IMAGE, content=_URI
        )
        self._build_query_message(msg)
        qm = self.query.related_query_messages.first()
        self.assertIsNotNone(qm)
        message = qm.to_openai_message()
        content = message["content"]
        self.assertIsInstance(content, list)
        types = {part["type"] for part in content}
        self.assertIn("image_url", types)
        self.assertIn("text", types)
        url_block = next(p for p in content if p["type"] == "image_url")
        self.assertEqual(url_block["image_url"]["url"], _URI)

    def test_image_token_estimate_is_fixed(self):
        msg = Message.objects.create(role=MessageRole.USER, session=self.sv.session, session_version=self.sv)
        msg.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.IMAGE, content=_URI
        )
        self._build_query_message(msg)
        qm = self.query.related_query_messages.first()
        qm.to_openai_message()
        self.assertTrue(IMAGE_TOKEN_ESTIMATE < qm.tokens < IMAGE_TOKEN_ESTIMATE + 500, qm.tokens)

    def test_estimate_message_tokens_uses_fixed_image_rate(self):
        msg = Message.objects.create(role=MessageRole.USER, session=self.sv.session, session_version=self.sv)
        msg.add_part(
            type=MessagePartType.MESSAGE, content_type=MessageContentType.IMAGE, content=_URI
        )
        # Image priced at the fixed per-image rate plus a few structural tokens
        # for the surrounding message dict — nothing proportional to the base64.
        self.assertEqual(estimate_message_tokens(msg), 1526)


class ToolImageResultTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.session, cls.sv = _make_session()
        cls.query = Query.objects.create(session=cls.sv.session, session_version=cls.sv)

    def test_tool_result_with_data_uri_becomes_image_url_block(self):
        from server.models.queries.query import QueryMessage
        qm = QueryMessage.objects.create(query=self.query, role=MessageRole.USER, source_message=None)

        tc = mock.Mock()
        tc.pk = 777
        tc.get_result.return_value = {
            "status": "success",
            "content_type": "image",
            "path": "/tmp/photo.jpg",
            "width": 2048,
            "height": 1024,
            "image": _URI,
        }
        content = qm._build_tool_message_content(tc.get_result())
        self.assertIsInstance(content, list)
        text = next(c for c in content if c["type"] == "text")
        url = next(c for c in content if c["type"] == "image_url")
        self.assertNotIn(_URI, text["text"])
        self.assertEqual(url["image_url"]["url"], _URI)

    def test_tool_result_without_image_stays_text(self):
        from server.models.queries.query import QueryMessage
        qm = QueryMessage.objects.create(query=self.query, role=MessageRole.USER, source_message=None)
        content = qm._build_tool_message_content({"status": "success", "type": "directory"})
        self.assertIsInstance(content, str)
        self.assertIn("directory", content)


class VisionGateTest(TestCase):
    def setUp(self):
        self.session, self.sv = _make_session()
        self.provider = ApiProvider.objects.create(name="vp")
        self.text_model = AiModel.objects.create(
            api_provider=self.provider, name="Text-Only-1", provider_model_id="text"
        )
        self.vision_model = AiModel.objects.create(
            api_provider=self.provider, name="Vision-1", provider_model_id="vision", vision=True
        )

    def _image_parts(self):
        return [{
            "type": "MESSAGE", "content_type": "IMAGE", "content": _URI,
        }]

    def test_blocks_image_for_non_vision_model(self):
        with mock.patch.object(Session, "aimodel", new_callable=mock.PropertyMock, return_value=self.text_model):
            with self.assertRaises(TypeError) as ctx:
                self.session.add_user_message(self._image_parts())
        message = str(ctx.exception)
        self.assertIn("not vision-capable", message)
        self.assertIn("Vision-1", message)
        self.assertIn("Text-Only-1", message)

    def test_allows_image_for_vision_model(self):
        with mock.patch.object(Session, "aimodel", new_callable=mock.PropertyMock, return_value=self.vision_model):
            with mock.patch.object(self.session, "get_task", return_value=mock.MagicMock()) as get_task:
                self.session.add_user_message(self._image_parts())
        get_task.assert_called_once_with("ingest_user_message")

    def test_allows_text_for_non_vision_model(self):
        with mock.patch.object(Session, "aimodel", new_callable=mock.PropertyMock, return_value=self.text_model):
            with mock.patch.object(self.session, "get_task", return_value=mock.MagicMock()):
                self.session.add_user_message([
                    {"type": "MESSAGE", "content_type": "TEXT", "content": "hello"},
                ])


class FromFileTest(TestCase):
    def test_image_file_stored_as_data_uri(self):
        import base64
        import os
        import tempfile

        from server.models.content import ContentType

        raw = b"\x89PNG\r\n\x1a\nfakepixel"
        tmp_path = None
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
            fh.write(raw)
            tmp_path = fh.name
        try:
            gc = GenericContent.from_file(tmp_path)
            self.assertEqual(gc.content_type, ContentType.IMAGE)
            self.assertEqual(gc.get(), f"data:image/png;base64,{base64.b64encode(raw).decode()}")
        finally:
            os.unlink(tmp_path)