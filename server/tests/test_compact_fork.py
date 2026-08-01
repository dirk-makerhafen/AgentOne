"""Regression tests for the message-chain integrity invariant during compaction.

``ingest_compaction`` inserts a COMPACTION boundary message immediately after
the last compacted message and keeps the compacted range in the chain.  The
chain must remain a single linear linked list with exactly one
``filter(next_messages=None)`` tail per session, and the compacted messages
must stay reachable (so the UI can still render the full history in order).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message, MessagePart
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel

_INGEST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "scripts" / "core" / "ingest_compaction.py"
)


def _load_ingest():
    spec = importlib.util.spec_from_file_location("_manifest_ingest_compaction", _INGEST_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _msg(sv, role, text, prev=None):
    m = Message.objects.create(session_version=sv, role=role, prev_message=prev)
    MessagePart.objects.create(
        message=m,
        type=MessagePartType.MESSAGE,
        content=GenericContent.from_text(text),
        content_type=MessageContentType.TEXT,
    )
    return m


class CompactionForkTest(TestCase):
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
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        self.session.refresh_from_db()
        self.ingest = _load_ingest()

    def _run_compaction(self, compacted, trigger, summary="summary"):
        from runtime.session.session import Session
        query = Query.objects.create(session_version=self.sv, trigger_message=trigger)
        for m in compacted:
            query.add_message(role=m.role, source_message=m).save()
        response = Response.objects.create(query=query, session_version=self.sv)
        session = Session(session_model=self.session)
        return self.ingest.ingest_compaction(
            session, response, [{"type": "message", "content": summary}]
        )

    def _tails(self):
        return list(Message.objects.filter(
            session_version=self.sv,
        ).filter(next_messages=None).order_by("pk").values_list("pk", flat=True))

    def test_partial_compaction_preserves_chain(self):
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)
        f = _msg(self.sv, MessageRole.USER, "f", e)

        out = self._run_compaction([c, d, e], trigger=f)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], f.pk)

        # Active chain: a -> b -> c -> d -> e -> compaction -> f
        f.refresh_from_db()
        comp = f.prev_message
        self.assertEqual(comp.pk, out["message"].pk)
        self.assertEqual(comp.prev_message_id, e.pk)  # newest_compacted
        self.assertTrue(comp.parts.filter(type="COMPACTION").exists())

        # Compacted range stays reachable, prev pointers intact (no orphaning)
        for msg, expected_prev in ((e, d), (d, c), (c, b)):
            self.assertEqual(msg.prev_message_id, expected_prev.pk)

    def test_full_compaction_preserves_chain(self):
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)

        out = self._run_compaction([a, b, c, d], trigger=d)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], out["message"].pk)  # compaction becomes the tail

        # Active chain: a -> b -> c -> d -> compaction
        comp = out["message"]
        self.assertEqual(comp.prev_message_id, d.pk)  # newest_compacted
        for msg, expected_prev in ((d, c), (c, b), (b, a), (a, None)):
            self.assertEqual(msg.prev_message_id, expected_prev.pk if expected_prev else None)

    def test_nothing_to_compact_no_fork(self):
        f = _msg(self.sv, MessageRole.USER, "f", None)
        out = self._run_compaction([], trigger=f)
        self.assertIsNotNone(out["message"])
        self.assertEqual(len(self._tails()), 1)

    def test_hidden_child_after_compaction_not_a_tail(self):
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)
        # hidden tool-result message between newest_compacted and first_kept
        h = _msg(self.sv, MessageRole.USER, "h", e)
        Message.objects.filter(pk=h.pk).update(hide_from_context=True)
        f = _msg(self.sv, MessageRole.USER, "f", h)

        self._run_compaction([c, d, e], trigger=f)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], f.pk)

        # Active chain: a -> b -> c -> d -> e -> compaction -> h -> f
        h.refresh_from_db()
        comp = h.prev_message
        self.assertEqual(comp.prev_message_id, e.pk)
        f.refresh_from_db()
        self.assertEqual(f.prev_message_id, h.pk)
