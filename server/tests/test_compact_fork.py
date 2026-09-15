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
    / ".agentone" / "scripts" / "compact" / "ingest_compaction.py"
)
_DECIDE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".agentone" / "scripts" / "core" / "decide_next_step.py"
)


def _load_ingest():
    spec = importlib.util.spec_from_file_location("_manifest_ingest_compaction", _INGEST_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_decide():
    spec = importlib.util.spec_from_file_location("_manifest_decide_next_step", _DECIDE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _msg(sv, role, text, prev=None):
    m = Message.objects.create(session=sv.session, session_version=sv, role=role, prev_message=prev)
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
        query = Query.objects.create(
            session=self.sv.session,
            session_version=self.sv,
            trigger_message=trigger
        )
        for m in compacted:
            query.add_message(role=m.role, source_message=m).save()
        response = Response.objects.create(query=query, session_version=self.sv, session=self.sv.session)
        session = Session(session_model=self.session)
        return self.ingest.ingest_compaction(
            session, response, [{"type":  MessagePartType.MESSAGE, "content": summary}]
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
        self.assertTrue(comp.parts.filter(type=MessagePartType.COMPACTION).exists())

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

    def test_second_compaction_boundary_follows_chain_not_pk(self):
        # A prior compaction inserted marker X mid-chain.  X was created
        # AFTER c (higher pk) but sits BEFORE it in the chain.  The second
        # compaction's boundary must be the chain-last compacted message (c),
        # NOT the pk-max message (X) — otherwise c stays in the context even
        # though it was compacted.
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)

        # Simulate compaction 1: marker X inserted between b and c.
        x = Message.objects.create(session=self.sv.session, session_version=self.sv, role=MessageRole.USER, prev_message=b)
        MessagePart.objects.create(
            message=x,
            type=MessagePartType.COMPACTION,
            content=GenericContent.from_text("old summary"),
            content_type=MessageContentType.TEXT,
        )
        Message.objects.filter(pk=c.pk).update(prev_message=x)

        # Second compaction: compact [X, c], keep d.
        out = self._run_compaction([x, c], trigger=d)

        # New boundary sits after c (chain-last compacted), and d points back
        # to it — NOT after X (which has the higher pk).
        self.assertEqual(out["message"].prev_message_id, c.pk)
        d.refresh_from_db()
        self.assertEqual(d.prev_message_id, out["message"].pk)
        self.assertEqual(len(self._tails()), 1, f"expected single tail, got {self._tails()}")
        self.assertEqual(self._tails()[0], d.pk)

    def test_stacked_markers_boundary_is_chain_tail_not_pk_max(self):
        # Regression for the real-world corruption: when a session compacts on
        # every turn, each new COMPACTION marker M_high is created AFTER the
        # previously kept message (higher pk) but inserted BEFORE it in the
        # chain, stacking markers into a run.  The pk-max message of the
        # compacted set is then the chain-HEAD of that run (oldest in chain),
        # and the true chain-last compacted message sits at the far end.
        # The boundary must follow the chain, not pk, so the kept region is
        # actually excluded from the context.
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)
        f = _msg(self.sv, MessageRole.USER, "f", e)

        # Stack two markers into a run between b and c.  Each marker has a
        # HIGHER pk than c but sits BEFORE it in the chain.
        def _marker(prev):
            m = Message.objects.create(session=self.sv.session, session_version=self.sv, role=MessageRole.USER, prev_message=prev)
            MessagePart.objects.create(
                message=m,
                type=MessagePartType.COMPACTION,
                content=GenericContent.from_text("old summary"),
                content_type=MessageContentType.TEXT,
            )
            return m

        m_low = _marker(b)      # oldest of the run, prev -> b
        m_high = _marker(m_low)  # pk-max, prev -> m_low
        Message.objects.filter(pk=c.pk).update(prev_message=m_high)
        self.assertGreater(m_high.pk, c.pk)
        self.assertGreater(m_low.pk, c.pk)

        # Compact everything through c, keeping d -> e -> f.
        out = self._run_compaction([a, b, m_low, m_high, c], trigger=f)

        # Boundary sits after c (chain-last compacted), NOT after m_high
        # (pk-max).  d must point back to the new marker.
        self.assertEqual(out["message"].prev_message_id, c.pk)
        d.refresh_from_db()
        self.assertEqual(d.prev_message_id, out["message"].pk)
        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], f.pk)

        # Active chain: a -> b -> m_low -> m_high -> c -> compaction -> d -> e -> f
        f.refresh_from_db()
        self.assertEqual(f.prev_message_id, e.pk)
        self.assertEqual(e.prev_message_id, d.pk)

    def test_marker_with_missing_successor_boundary_follows_chain_tail(self):
        # Regression for the real-world failure: the compaction query starts
        # with the prior COMPACTION marker (the walk-back stops there), but the
        # marker's immediate chain-successor is NOT in the compacted set (e.g. a
        # hidden tool-result message between the marker and the rest).  Sorting
        # by pk — or walking from the chain head — would pick the marker as the
        # "newest" compacted message (its prev is outside the set, and its own
        # next is missing), chaining new markers into a run and leaving the live
        # conversation un-compacted.  The boundary must land after the chain-LAST
        # compacted message.
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)

        # Prior compaction marker X inserted between b and c (created after d,
        # so higher pk, yet sits BEFORE it in the chain).
        x = Message.objects.create(session=self.sv.session, session_version=self.sv, role=MessageRole.USER, prev_message=b)
        MessagePart.objects.create(
            message=x,
            type=MessagePartType.COMPACTION,
            content=GenericContent.from_text("old summary"),
            content_type=MessageContentType.TEXT,
        )
        # Hidden tool-result between X and c — present in the chain but excluded
        # from the compaction query (hide_from_context), so the marker's chain
        # successor is missing from the compacted set.
        h = _msg(self.sv, MessageRole.USER, "h", x)
        Message.objects.filter(pk=h.pk).update(hide_from_context=True)
        Message.objects.filter(pk=c.pk).update(prev_message=h)
        self.assertGreater(x.pk, d.pk)

        # Second compaction: compact [X, c, d] (h excluded), keep e.
        out = self._run_compaction([x, c, d], trigger=e)

        # Boundary sits after d (chain-last compacted), NOT after X (pk-max).
        self.assertEqual(out["message"].prev_message_id, d.pk)
        e.refresh_from_db()
        self.assertEqual(e.prev_message_id, out["message"].pk)
        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], e.pk)

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

    def test_fork_flow_inserts_marker_from_child_result(self):
        """The auto-compaction (fork) path: ``boundary_pk`` + ``result`` where
        ``result`` is the child's final Message.  The child's summary arrives as
        a MESSAGE part (``ingest_assistant_message`` converts the child's
        ``final_result`` TOOLCALL into a MESSAGE part), and the marker lands
        right after the boundary message."""
        from runtime.session.session import Session

        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)

        # Child session (SUBTASK_FORK) whose last message carries the summary.
        child_model = SessionModel.objects.create(name="compaction-child", session_type="subtask_fork")
        child_sv = SessionVersionModel.objects.create(
            session=child_model,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=child_model.pk).update(latest_session_version=child_sv)
        child_msg = _msg(child_sv, MessageRole.ASSISTANT, "child summary content", None)

        session = Session(session_model=self.session)
        out = self.ingest.ingest_compaction(
            session, boundary_pk=c.pk, result=child_msg
        )

        marker = out["message"]
        self.assertEqual(marker.prev_message_id, c.pk)
        d.refresh_from_db()
        self.assertEqual(d.prev_message_id, marker.pk)
        self.assertTrue(marker.parts.filter(type=MessagePartType.COMPACTION).exists())
        comp_text = "".join(
            str(p.content.get()) for p in marker.parts.all() if p.content
        )
        self.assertIn("child summary content", comp_text)

        # Single linear chain with one tail.
        tails = self._tails()
        self.assertEqual(len(tails), 1, f"expected single tail, got {tails}")
        self.assertEqual(tails[0], d.pk)

    def test_fork_flow_final_result_toolcall_part_extracts_summary(self):
        """When the child's result message still contains a TOOLCALL part for
        ``final_result`` (not yet converted), its content argument is used."""
        from runtime.session.session import Session
        from server.models.tasks.task_definition import TaskDefinition
        from server.models.tasks.task_definition_version import TaskDefinitionVersion
        from server.models.tasks.agent_task_call import AgentTaskCall

        a = _msg(self.sv, MessageRole.USER, "a", None)
        _msg(self.sv, MessageRole.USER, "b", a)

        td = TaskDefinition.objects.create(name="final_result", group_name="")
        TaskDefinitionVersion.objects.create(
            task_definition=td,
            description="test",
            function_schema={"type": "object", "properties": {}},
        )
        toolcall = AgentTaskCall.objects.create(
            task_definition=td,
            session=self.sv.session,
            session_version=self.sv,
            carguments_json={},
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
        )
        result_msg = Message.objects.create(
            session=self.sv.session, session_version=self.sv, role=MessageRole.ASSISTANT
        )
        result_msg.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="prefix",
        )
        result_msg.add_part(
            type=MessagePartType.TOOLCALL,
            content_type=MessageContentType.JSON,
            content={"name": "final_result", "arguments": {}},
            tool_call=toolcall,
        )
        AgentTaskCall.objects.filter(pk=toolcall.pk).update(
            carguments_json={"content": "summary from final_result"}
        )

        session = Session(session_model=self.session)
        out = self.ingest.ingest_compaction(
            session, boundary_pk=a.pk, result=result_msg
        )

        marker = out["message"]
        comp_text = "".join(
            str(p.content.get()) for p in marker.parts.all() if p.content
        )
        self.assertIn("prefix", comp_text)
        self.assertIn("summary from final_result", comp_text)


class ForkSessionSettingsTest(TestCase):
    """Forks must inherit the parent's session settings, not agent defaults.

    Regression: forks only had the agent's defaults because no session settings
    were copied onto the child session version.  For a compaction fork this is
    dangerous — the fork carries the same oversized context that triggered the
    compaction, so if it inherits ``auto_compact_limit`` it immediately spawns
    another compaction fork (infinite chain).  ``get_or_create_session`` must
    clone the parent's settings, and the compaction fork must pin
    ``auto_compact_limit=0``.
    """

    def setUp(self):
        self.agent = AgentModel.objects.create(name="test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(),
        )
        self.session = SessionModel.objects.create(name="parent-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(latest_session_version=self.sv)
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)
        self.session.refresh_from_db()

    def test_fork_inherits_parent_session_settings(self):
        """A fork copies the parent's session settings row."""
        parent_settings = SettingsModel.objects.create(
            auto_compact_limit=150000,
            max_retries=3,
            disallowedTaskNames=["bad_task"],
        )
        SessionVersionModel.objects.filter(pk=self.sv.pk).update(
            session_settings=parent_settings
        )
        self.sv.refresh_from_db()

        child_sv = self.av.get_or_create_session(
            name=f"fork-{self.sv.pk}",
            parent_session_version=self.sv,
            session_type="subtask_fork",
        )
        self.assertIsNotNone(child_sv.session_settings)
        self.assertNotEqual(child_sv.session_settings.pk, parent_settings.pk)
        self.assertEqual(child_sv.session_settings.auto_compact_limit, 150000)
        self.assertEqual(child_sv.session_settings.max_retries, 3)
        self.assertEqual(child_sv.session_settings.disallowedTaskNames, ["bad_task"])

        # The parent's row is untouched (immutable snapshot semantics).
        parent_settings.refresh_from_db()
        self.assertEqual(parent_settings.auto_compact_limit, 150000)

    def test_fork_without_parent_settings_keeps_agent_defaults(self):
        """No parent session settings → child stays on agent defaults (None)."""
        child_sv = self.av.get_or_create_session(
            name=f"fork-none-{self.sv.pk}",
            parent_session_version=self.sv,
            session_type="subtask_delegate",
        )
        self.assertIsNone(child_sv.session_settings)

    def test_compaction_fork_pins_auto_compact_limit_zero(self):
        """The stable knob the compaction fork uses to stop re-forking."""

        parent_settings = SettingsModel.objects.create(
            auto_compact_limit=120000,
            reasoning_effort="medium",
        )
        fork_settings = self.av.clone_settings(parent_settings, auto_compact_limit=0)
        self.assertEqual(fork_settings.auto_compact_limit, 0)
        self.assertEqual(fork_settings.reasoning_effort, "medium")
        self.assertNotEqual(fork_settings.pk, parent_settings.pk)

    def test_decide_falls_back_to_parent_message_when_parts_missing(self):
        """Retry-flattened resume (parts_vs_message.md §8): after a
        compaction retry the wrapper's dict *is* decide's kwargs, with the
        compact chain's empty response/parts.  The turn must still be read
        off the parent assistant message — here its "?"-ending text ends
        the turn instead of looping."""
        from types import SimpleNamespace

        from server.models.enums.session_enums import SessionType

        decide = _load_decide()
        parent = _msg(self.sv, MessageRole.ASSISTANT, "Shall I proceed?", None)
        marker = _msg(self.sv, MessageRole.USER, "summary", parent)
        session = SimpleNamespace(
            count_turn=lambda: None,
            count_unattended_turn=lambda: None,
            max_turns=None,
            max_unattended_turns=None,
            current_turn_count=0,
            current_unattended_turn_count=0,
            session_type=SessionType.SESSION,
            _get_session_setting=lambda name: False,
            get_task=lambda name: MagicMock(),
        )
        out = decide.decide_next_step(
            session, None, None, marker, parent_message=parent,
        )
        self.assertIs(out, marker)

    def test_decide_without_fallback_still_sees_no_tool_calls(self):
        """Control: without parent_message, parts=None behaves as before
        (no tool calls, no message) — the fallback only triggers on the
        retry-flattened shape."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from server.models.enums.session_enums import SessionType

        decide = _load_decide()
        marker = _msg(self.sv, MessageRole.USER, "summary", None)
        session = SimpleNamespace(
            count_turn=lambda: None,
            count_unattended_turn=lambda: None,
            max_turns=None,
            max_unattended_turns=None,
            current_turn_count=0,
            current_unattended_turn_count=0,
            session_type=SessionType.SESSION,
            _get_session_setting=lambda name: False,
            get_task=lambda name: MagicMock(),
        )
        next_turn = decide.decide_next_step(session, None, [], marker)
        self.assertIsNotNone(next_turn)
