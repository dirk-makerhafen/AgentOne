"""Regression tests for the I7 message-chain fork invariant.

Covers the compaction-fork bug: ``ingest_compaction`` must leave exactly one
``filter(next_messages=None)`` tail per session, and orphaned compacted
messages must be self-referenced (I8) so they never appear as a second tail.
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

    def test_partial_compaction_leaves_single_tail(self):
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)
        f = _msg(self.sv, MessageRole.USER, "f", e)

        self._run_compaction([c, d, e], trigger=f)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], f.pk)

        # Active chain: b -> compaction -> f
        f.refresh_from_db()
        comp = f.prev_message
        self.assertEqual(comp.prev_message_id, b.pk)

        # Compacted orphans are self-referenced (I8) so never tails again
        for orphan in (c, d, e):
            orphan.refresh_from_db()
            self.assertEqual(orphan.prev_message_id, orphan.pk)

    def test_full_compaction_leaves_single_tail(self):
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)

        self._run_compaction([a, b, c, d], trigger=d)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], d.pk)

        for orphan in (a, b, c):
            orphan.refresh_from_db()
            self.assertEqual(orphan.prev_message_id, orphan.pk)

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
        f = _msg(self.sv, MessageRole.USER, "f", e)
        # hidden tool-result message between newest_compacted and first_kept
        h = _msg(self.sv, MessageRole.USER, "h", e)
        Message.objects.filter(pk=h.pk).update(hide_from_context=True)

        self._run_compaction([c, d, e], trigger=f)

        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], f.pk)
