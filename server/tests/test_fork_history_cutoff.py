"""Regression tests for fork history boundaries in ``build_llm_context``.

A fork grafts its chain onto a parent message via a hidden anchor
(``Session.link_history_to``).  Compaction later splices a COMPACTION marker
into that parent chain *behind* the anchor, with a newer pk.  The context walk
must treat such a marker as a later mutation and keep walking, while a marker
that predates the fork still terminates the segment.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from django.test import TestCase

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.message_enums import (
    MessageContentType,
    MessagePartType,
    MessageRole,
    MessageType,
)
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel

_CONTEXT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "scripts" / "core" / "build_llm_context.py"
)


def _load_context():
    spec = importlib.util.spec_from_file_location("_manifest_build_llm_context", _CONTEXT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _runtime(name: str, session_type: str = ""):
    agent = AgentModel.objects.create(name=f"agent-{uuid.uuid4().hex[:8]}")
    av = AgentVersionModel.objects.create(
        agent=agent,
        agent_settings=SettingsModel.objects.create(max_history_messages=100),
    )
    session = SessionModel.objects.create(name=name, session_type=session_type)
    sv = SessionVersionModel.objects.create(
        session=session,
        agent=agent,
        pinned_agent_version=av,
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    session.refresh_from_db()
    return Session(session_model=session), sv


def _msg(
    sv,
    text: str,
    *,
    role: str = MessageRole.USER,
    message_type: str | None = None,
    prev=None,
    hidden: bool = False,
    pinned: bool = False,
    part_type: str = MessagePartType.MESSAGE,
):
    message = Message.objects.create(
        session=sv.session,
        session_version=sv,
        role=role,
        message_type=message_type or MessageType.DEFAULT,
        prev_message=prev,
        hide_from_context=hidden,
        pin_to_context=pinned,
    )
    message.add_part(type=part_type, content_type=MessageContentType.TEXT, content=text)
    return message


def _chain(sv, labels, prev=None):
    """Create ``labels`` as a single oldest -> newest ``prev_message`` chain."""
    result = []
    for label in labels:
        prev = _msg(sv, label, prev=prev)
        result.append(prev)
    return result


def _fork(sv, anchor, labels):
    """Build a hook-style fork: hidden anchor + synthetic messages."""
    hidden = _msg(
        sv,
        "fork anchor",
        role=MessageRole.INFO,
        message_type=MessageType.INFO,
        prev=anchor,
        hidden=True,
    )
    chain = _chain(sv, labels, prev=hidden)
    return chain[-1], chain


def _source_pks(query):
    return set(
        query.related_query_messages.exclude(source_message=None)
        .values_list("source_message_id", flat=True)
    )


class ForkHistoryCutoffTest(TestCase):
    def setUp(self):
        self.context = _load_context()

    def test_late_compaction_marker_does_not_truncate_fork_history(self):
        parent, sv = _runtime("parent")
        messages = _chain(sv, ["p1", "p2", "p3", "p4", "p5"])
        child, child_sv = _runtime("child", "subtask_hook")
        trigger, fork_messages = _fork(child_sv, messages[-1], ["notice", "prompt"])

        # Compaction happens after the fork: the marker is newer than the
        # anchor but is spliced behind it in chain order.
        marker = _msg(sv, "summary", message_type=MessageType.COMPACTION,
                      part_type=MessagePartType.COMPACTION, prev=messages[1])
        Message.objects.filter(pk=messages[2].pk).update(prev_message=marker)

        trigger = Message.objects.get(pk=trigger.pk)
        pks = _source_pks(self.context.build_llm_context(child, trigger))
        self.assertTrue({m.pk for m in messages}.issubset(pks))
        self.assertTrue({m.pk for m in fork_messages}.issubset(pks))
        self.assertNotIn(marker.pk, pks)

    def test_preexisting_compaction_marker_still_stops_walk(self):
        parent, sv = _runtime("parent")
        messages = _chain(sv, ["p1", "p2", "p3", "p4", "p5"])
        # Marker created before the fork, so its pk is older than the anchor.
        marker = _msg(sv, "old summary", message_type=MessageType.COMPACTION,
                      part_type=MessagePartType.COMPACTION, prev=messages[1])
        Message.objects.filter(pk=messages[2].pk).update(prev_message=marker)

        child, child_sv = _runtime("child", "subtask_hook")
        trigger, fork_messages = _fork(child_sv, messages[-1], ["notice", "prompt"])
        # Re-fetch: production gets the trigger from the DB, so cached
        # in-memory ``prev_message`` pointers from chain construction do not
        # hide the relink above.
        trigger = Message.objects.get(pk=trigger.pk)
        pks = _source_pks(self.context.build_llm_context(child, trigger))
        self.assertNotIn(messages[0].pk, pks)
        self.assertNotIn(messages[1].pk, pks)
        self.assertTrue({m.pk for m in messages[2:]}.issubset(pks))
        self.assertTrue({m.pk for m in fork_messages}.issubset(pks))

    def test_fork_anchored_on_info_toast_ignores_later_marker(self):
        """``session_end`` reflection can fork from a UI-only success toast."""
        parent, sv = _runtime("parent")
        messages = _chain(sv, ["p1", "p2", "p3", "p4"])
        toast = _msg(
            sv,
            "Compaction successful",
            role=MessageRole.INFO,
            message_type=MessageType.INFO,
            prev=messages[-1],
            hidden=True,
        )
        child, child_sv = _runtime("child", "subtask_hook")
        trigger, fork_messages = _fork(child_sv, toast, ["notice", "prompt"])

        marker = _msg(sv, "summary", message_type=MessageType.COMPACTION,
                      part_type=MessagePartType.COMPACTION, prev=messages[1])
        Message.objects.filter(pk=messages[2].pk).update(prev_message=marker)

        trigger = Message.objects.get(pk=trigger.pk)
        pks = _source_pks(self.context.build_llm_context(child, trigger))
        self.assertTrue({m.pk for m in messages}.issubset(pks))
        self.assertTrue({m.pk for m in fork_messages}.issubset(pks))
        self.assertNotIn(marker.pk, pks)

    def test_nested_forks_apply_cutoff_per_parent_session(self):
        parent, parent_sv = _runtime("parent")
        parent_messages = _chain(parent_sv, ["p1", "p2", "p3", "p4"])

        child, child_sv = _runtime("child", "subtask_hook")
        child_trigger, child_messages = _fork(child_sv, parent_messages[2], ["c1", "c2"])

        grandchild, grandchild_sv = _runtime("grandchild", "subtask_hook")
        trigger, grandchild_messages = _fork(grandchild_sv, child_trigger, ["g1", "g2"])

        # Late marker in the grandparent, inserted after both forks.
        marker = _msg(parent_sv, "late summary", message_type=MessageType.COMPACTION,
                      part_type=MessagePartType.COMPACTION, prev=parent_messages[1])
        Message.objects.filter(pk=parent_messages[2].pk).update(prev_message=marker)

        trigger = Message.objects.get(pk=trigger.pk)
        pks = _source_pks(self.context.build_llm_context(grandchild, trigger))
        self.assertTrue({m.pk for m in grandchild_messages}.issubset(pks))
        self.assertTrue({m.pk for m in child_messages}.issubset(pks))
        self.assertTrue({m.pk for m in parent_messages[:3]}.issubset(pks))
        self.assertNotIn(marker.pk, pks)

    def test_late_pinned_bootstrap_is_not_filtered(self):
        """Only COMPACTION is time-filtered; back-spliced pins stay visible."""
        parent, sv = _runtime("parent")
        messages = _chain(sv, ["p1", "p2", "p3", "p4"])
        child, child_sv = _runtime("child", "subtask_hook")
        trigger, fork_messages = _fork(child_sv, messages[-1], ["notice", "prompt"])

        # Pinned bootstrap created after the fork but spliced at the front of
        # the segment (newer pk, older chain position) — must still be loaded.
        bootstrap = _msg(sv, "pinned guidance", pinned=True, prev=messages[0])
        Message.objects.filter(pk=messages[1].pk).update(prev_message=bootstrap)

        trigger = Message.objects.get(pk=trigger.pk)
        pks = _source_pks(self.context.build_llm_context(child, trigger))
        self.assertIn(bootstrap.pk, pks)
        self.assertTrue({m.pk for m in messages}.issubset(pks))
        self.assertTrue({m.pk for m in fork_messages}.issubset(pks))
