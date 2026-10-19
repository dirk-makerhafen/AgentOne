"""Dispatch tests for session hooks (see ``docs/session-hooks.md`` §§5–9, 12).

``maybe_fire_hooks`` is exercised for real (fork building, budgets, run
rows); task execution is faked at the ``Session.get_task`` seam (same
pattern as ``test_idle_compact.py``) — no celery, no LLM. Script wiring
(``decide_next_step``, ``build_llm_compact_context``, ``ingest_compaction``,
``set_is_active``) is verified with ``maybe_fire_hooks`` mocked, asserting
event + snapshot context.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from runtime.hooks import matches, maybe_fire_hooks, reap_hook_timeouts
from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.enums.session_enums import SessionType
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskType
from server.models.hooks.hook_run import SessionHookRun
from server.models.message import Message, MessagePart
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.tests.helpers import create_global_task

_REPO = Path(__file__).resolve().parent.parent.parent


def _load_script(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _REPO / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _msg(sv, role, text, prev=None):
    m = Message.objects.create(
        session=sv.session, session_version=sv, role=role, prev_message=prev
    )
    MessagePart.objects.create(
        message=m,
        type=MessagePartType.MESSAGE,
        content=GenericContent.from_text(text),
        content_type=MessageContentType.TEXT,
    )
    return m


class FakeTask:
    """Stand-in for a BoundTask — records ``delay`` kwargs, returns a call."""

    def __init__(self, test, name):
        self.test = test
        self.name = name
        self.calls: list[tuple[tuple, dict]] = []

    def delay(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.returned = self.test._make_call()
        return self.returned


def _hook_entry(**over):
    entry = {
        "name": "probe",
        "on": "stop",
        "task": "probe_task",
        "max_tokens": 40000,
        "timeout_seconds": 300,
    }
    entry.update(over)
    return entry


class HookDispatchTest(TestCase):
    def setUp(self):
        td = create_global_task(f"hook-probe-{uuid.uuid4().hex[:6]}", "core", TaskType.TASK)
        td.refresh_from_db()
        self.tdv = td.latest_task_version
        self.agent = AgentModel.objects.create(name=f"hook-agent-{uuid.uuid4().hex[:6]}")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
            agent_settings=SettingsModel.objects.create(max_history_messages=100),
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av
        )
        self.agent.refresh_from_db()
        self.session = SessionModel.objects.create(
            name=f"hook-session-{uuid.uuid4().hex[:6]}"
        )
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        self.runtime = Session(session_model=self.session)
        self.fakes: dict[str, FakeTask] = {}

    # -- helpers ------------------------------------------------------

    def _set_hooks(self, entries):
        AgentVersionModel.objects.filter(pk=self.av.pk).update(hooks=entries)
        self.av.refresh_from_db()

    def _make_call(self):
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.task_instance import TaskInstance

        ti = TaskInstance.get_or_create(
            task_definition=self.tdv,
            session_version=self.sv,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1,
            max_retries=0,
            retry_delay=10,
            retry_requires_approval=True,
        )
        return AgentTaskCall.create(task_instance=ti, kwargs={})

    def _route_tasks(self):
        def router(name):
            if name not in self.fakes:
                self.fakes[name] = FakeTask(self, name)
            return self.fakes[name]

        patcher = patch.object(Session, "get_task", side_effect=router)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _chain(self, n=8):
        prev = None
        msgs = []
        for i in range(n):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            prev = _msg(
                self.sv, role,
                f"message number {i} with enough words to count tokens easily",
                prev,
            )
            msgs.append(prev)
        return msgs

    # -- matcher ------------------------------------------------------

    def test_matches_table(self):
        ctx = {"session_type": "session", "trigger": "auto", "reason": "x"}
        self.assertTrue(matches(None, "stop", ctx))
        self.assertTrue(matches("session", "stop", ctx))
        self.assertFalse(matches("subsession", "stop", ctx))
        self.assertTrue(matches("session|subsession", "stop", {"session_type": "subsession"}))
        self.assertTrue(matches(".*", "stop", ctx))
        self.assertTrue(matches("auto|idle", "pre_compact", ctx))
        self.assertFalse(matches("manual", "pre_compact", ctx))
        self.assertTrue(
            matches("allowlist_violation", "session_end", {"reason": "allowlist_violation"})
        )
        self.assertFalse(matches("[", "stop", ctx))  # bad regex never matches

    def test_unknown_event_ignored(self):
        self._set_hooks([_hook_entry()])
        self.assertEqual(maybe_fire_hooks(self.runtime, "bogus", {}), [])

    # -- gates --------------------------------------------------------

    def test_hook_fork_never_refires(self):
        self._set_hooks([_hook_entry()])
        hook_session = SessionModel.objects.create(
            name=f"hook-fork-{uuid.uuid4().hex[:6]}",
            session_type=SessionType.SUBTASK_HOOK.value,
        )
        hook_sv = SessionVersionModel.objects.create(
            session=hook_session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=hook_session.pk).update(
            latest_session_version=hook_sv
        )
        fork = Session(session_model=hook_session)
        self._route_tasks()
        self.assertEqual(maybe_fire_hooks(fork, "stop", {}), [])
        self.assertEqual(SessionHookRun.objects.count(), 0)
        self.assertEqual(self.fakes, {})

    def test_missing_hook_agent_skipped(self):
        self._set_hooks([_hook_entry(agent="no_such_agent")])
        self._route_tasks()
        self.assertEqual(maybe_fire_hooks(self.runtime, "stop", {}), [])
        self.assertEqual(SessionHookRun.objects.count(), 0)

    def test_in_flight_hook_not_redispatched(self):
        self._set_hooks([_hook_entry()])
        call = self._make_call()
        SessionHookRun.objects.create(
            session=self.session, hook_name="probe", event="stop",
            root_call=call, status="dispatched",
        )
        self._route_tasks()
        self.assertEqual(maybe_fire_hooks(self.runtime, "stop", {}), [])
        self.assertEqual(self.fakes, {})

    def test_ended_run_may_fire_again(self):
        from server.models.tasks.agent_task_call import AgentTaskCall

        self._set_hooks([_hook_entry()])
        call = self._make_call()
        AgentTaskCall.objects.filter(pk=call.pk).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        SessionHookRun.objects.create(
            session=self.session, hook_name="probe", event="stop",
            root_call=call, status="dispatched",
        )
        self._route_tasks()
        msgs = self._chain(2)
        runs = maybe_fire_hooks(
            self.runtime, "stop", {"anchor_message": msgs[-1].pk}
        )
        self.assertEqual(len(runs), 1)

    # -- fork building -------------------------------------------------

    def test_fire_builds_pinned_fork_and_run_row(self):
        self._set_hooks([_hook_entry(timeout_seconds=60)])
        self._route_tasks()
        msgs = self._chain(4)
        before = __import__("django.utils.timezone", fromlist=["now"]).now()
        runs = maybe_fire_hooks(
            self.runtime, "stop", {"anchor_message": msgs[-1].pk}
        )
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.hook_name, "probe")
        self.assertEqual(run.event, "stop")
        self.assertEqual(run.anchor_message_id, msgs[-1].pk)
        self.assertIsNotNone(run.root_call_id)
        self.assertEqual(run.status, "dispatched")
        self.assertGreaterEqual(run.deadline, before)

        fork_session = SessionModel.objects.get(
            name__startswith=f"p{self.session.pk}:hook:probe:"
        )
        self.assertEqual(fork_session.session_type, SessionType.SUBTASK_HOOK.value)
        fork_sv = fork_session.latest_session_version
        self.assertEqual(fork_sv.session_settings.auto_compact_max_tokens, 0)
        self.assertEqual(fork_sv.session_settings.auto_compact_idle_seconds, 0)

        # Fork chain anchored at the snapshot message: only the hidden fork
        # anchor is persisted synchronously; the two hook instruction messages
        # are persisted asynchronously by the ingest_user_message call the
        # hook task depends on.
        hook_msgs = list(
            Message.objects.filter(session_version=fork_sv).order_by("pk")
        )
        self.assertEqual(len(hook_msgs), 1)
        self.assertEqual(hook_msgs[0].prev_message_id, msgs[-1].pk)
        self.assertTrue(hook_msgs[0].hide_from_context)

        ingest_fake = self.fakes["ingest_user_message"]
        self.assertEqual(len(ingest_fake.calls), 1)
        ingest_kwargs = ingest_fake.calls[0][1]
        self.assertFalse(ingest_kwargs["execute_turn"])
        self.assertEqual(len(ingest_kwargs["message"]), 2)
        self.assertEqual(ingest_kwargs["message"][0]["role"], MessageRole.USER)
        self.assertIn(
            "session-hook worker",
            ingest_kwargs["message"][0]["parts"][0]["content"],
        )

        # Hook task dispatched with JSON-safe context, depending on the
        # ingest call (auto-await resolves ``message`` to the last hook msg).
        fake = self.fakes["probe_task"]
        self.assertEqual(len(fake.calls), 1)
        kwargs = fake.calls[0][1]
        self.assertEqual(kwargs["message"].pk, ingest_fake.returned.pk)
        self.assertNotIn("hook_after", kwargs)
        self.assertEqual(
            kwargs["hook_ctx"],
            {
                "hook": "probe",
                "event": "stop",
                "parent_session_pk": self.session.pk,
                "parent_agent": self.agent.name,
                "anchor_message_pk": msgs[-1].pk,
                "trigger": "",
                "reason": "",
            },
        )

    def test_over_budget_prefixes_compaction(self):
        self._set_hooks([_hook_entry(max_tokens=1)])
        self._route_tasks()
        msgs = self._chain(8)
        from runtime.history_limiter import find_compaction_boundary

        self.assertIsNotNone(find_compaction_boundary(self.runtime, msgs[-1]))
        runs = maybe_fire_hooks(
            self.runtime, "stop", {"anchor_message": msgs[-1].pk}
        )
        self.assertEqual(len(runs), 1)
        compact_fake = self.fakes["compact_turn"]
        self.assertEqual(len(compact_fake.calls), 1)
        hook_kwargs = self.fakes["probe_task"].calls[0][1]
        self.assertEqual(hook_kwargs["hook_after"].pk, compact_fake.returned.pk)

    def test_ingest_dispatched_on_parent_with_result(self):
        self._set_hooks([_hook_entry(ingest="record_memory")])
        self._route_tasks()
        msgs = self._chain(2)
        runs = maybe_fire_hooks(
            self.runtime, "stop", {"anchor_message": msgs[-1].pk}
        )
        self.assertEqual(len(runs), 1)
        ingest_fake = self.fakes["record_memory"]
        self.assertEqual(len(ingest_fake.calls), 1)
        kwargs = ingest_fake.calls[0][1]
        self.assertEqual(kwargs["result"].pk, runs[0].root_call_id)
        self.assertEqual(kwargs["hook_name"], "probe")
        self.assertIn("hook_ctx", kwargs)

    def test_snapshot_anchor_stable_when_parent_grows(self):
        self._set_hooks([_hook_entry()])
        self._route_tasks()
        msgs = self._chain(2)
        runs = maybe_fire_hooks(
            self.runtime, "stop", {"anchor_message": msgs[-1].pk}
        )
        anchor_pk = runs[0].anchor_message_id
        _msg(self.sv, MessageRole.USER, "arrived mid-reflection", msgs[-1])
        run = SessionHookRun.objects.get(pk=runs[0].pk)
        self.assertEqual(run.anchor_message_id, anchor_pk)
        fork_msgs = Message.objects.filter(
            session_version__session__name__startswith=f"p{self.session.pk}:hook:"
        ).order_by("pk")
        self.assertEqual(fork_msgs[0].prev_message_id, anchor_pk)

    # -- reaper --------------------------------------------------------

    def test_reaper_deletes_finished_and_cancels_expired(self):
        from datetime import timedelta
        from django.utils import timezone

        from server.models.tasks.agent_task_call import AgentTaskCall

        live = self._make_call()
        live2 = self._make_call()
        ended = self._make_call()
        AgentTaskCall.objects.filter(pk=ended.pk).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        )
        past = timezone.now() - timedelta(seconds=10)
        future = timezone.now() + timedelta(seconds=600)
        SessionHookRun.objects.create(
            session=self.session, hook_name="gone", event="stop",
            root_call=ended, status="dispatched",
        )
        expired_run = SessionHookRun.objects.create(
            session=self.session, hook_name="old", event="stop",
            root_call=live, deadline=past, status="dispatched",
        )
        future_run = SessionHookRun.objects.create(
            session=self.session, hook_name="fresh", event="stop",
            root_call=live2, deadline=future, status="dispatched",
        )
        self.assertEqual(reap_hook_timeouts(), 2)
        self.assertFalse(
            SessionHookRun.objects.filter(hook_name="gone").exists()
        )
        expired_run.refresh_from_db()
        self.assertEqual(expired_run.status, "expired")
        live.refresh_from_db()
        self.assertEqual(live.status_detail, TaskCallStatusDetail.ENDED_CANCELLED)
        # Future run untouched (also proves per-row handling, not bulk).
        self.assertTrue(
            SessionHookRun.objects.filter(pk=future_run.pk, status="dispatched").exists()
        )

    # -- script wiring --------------------------------------------------

    def test_decide_fires_stop(self):
        decide = _load_script(".agentone/scripts/core/decide_next_step.py", "hook_decide")
        msgs = self._chain(2)
        parts = [{"type": MessagePartType.MESSAGE, "content": "done"}]
        with patch("runtime.hooks.maybe_fire_hooks") as mfh:
            out = decide.decide_next_step(
                self.runtime, None, parts, msgs[-1], has_final_result=True
            )
        self.assertEqual(out.pk, msgs[-1].pk)
        mfh.assert_called_once()
        args, _ = mfh.call_args
        self.assertEqual(args[1], "stop")
        self.assertEqual(args[2]["anchor_message"], msgs[-1].pk)

    def test_decide_without_final_result_fires_nothing(self):
        decide = _load_script(".agentone/scripts/core/decide_next_step.py", "hook_decide2")
        msgs = self._chain(2)
        parts = [
            {"type": MessagePartType.MESSAGE, "content": "working"},
            {"tool_call": object()},
        ]
        self._route_tasks()
        with patch("runtime.hooks.maybe_fire_hooks") as mfh:
            decide.decide_next_step(
                self.runtime, None, parts, msgs[-1],
                has_final_result=False, has_tool_calls=True, has_message=True,
            )
        for call in mfh.call_args_list:
            self.assertNotEqual(call.args[1], "stop")

    def test_set_is_active_fires_session_end_once(self):
        tail = _msg(self.sv, MessageRole.USER, "hello", None)
        with patch("runtime.hooks.maybe_fire_hooks") as mfh:
            self.runtime.set_is_active(False, reason="test_reason")
        mfh.assert_called_once()
        args, _ = mfh.call_args
        self.assertEqual(args[1], "session_end")
        self.assertEqual(args[2]["reason"], "test_reason")
        self.assertIsNotNone(args[2]["anchor_message"])
        with patch("runtime.hooks.maybe_fire_hooks") as mfh2:
            self.runtime.set_is_active(False)  # no transition → silent
            self.runtime.set_is_active(True)  # reactivation → silent
        mfh2.assert_not_called()

    def test_build_fires_pre_compact_once(self):
        build = _load_script(
            ".agentone/scripts/compact/build_llm_compact_context.py", "hook_build"
        )
        msgs = self._chain(8)
        with (
            patch("runtime.hooks.maybe_fire_hooks") as mfh,
            patch("runtime.events.publish_model_event"),
            patch.object(Session, "add_user_message") as _,
        ):
            out = build.build_llm_compact_context(self.runtime, message=msgs[-1])
        self.assertIn("child_session_pk", out)
        mfh.assert_called_once()
        args, _ = mfh.call_args
        self.assertEqual(args[1], "pre_compact")
        self.assertEqual(args[2]["trigger"], "auto")
        self.assertEqual(args[2]["anchor_message"], msgs[-1].pk)

    def test_ingest_fires_post_compact_at_marker(self):
        ingest = _load_script(
            ".agentone/scripts/compact/ingest_compaction.py", "hook_ingest"
        )
        a = _msg(self.sv, MessageRole.USER, "a", None)
        b = _msg(self.sv, MessageRole.USER, "b", a)
        c = _msg(self.sv, MessageRole.USER, "c", b)
        d = _msg(self.sv, MessageRole.USER, "d", c)
        e = _msg(self.sv, MessageRole.USER, "e", d)
        f = _msg(self.sv, MessageRole.USER, "f", e)
        child_model = SessionModel.objects.create(
            name=f"hook-compaction-child-{uuid.uuid4().hex[:6]}",
            session_type="subtask_fork",
        )
        child_sv = SessionVersionModel.objects.create(
            session=child_model, agent=self.agent, pinned_agent_version=self.av
        )
        SessionModel.objects.filter(pk=child_model.pk).update(
            latest_session_version=child_sv
        )
        result_msg = _msg(child_sv, MessageRole.ASSISTANT, "summary", None)
        with patch("runtime.hooks.maybe_fire_hooks") as mfh:
            out = ingest.ingest_compaction(
                self.runtime,
                child_session_pk=child_model.pk,
                boundary_pk=e.pk,
                result=result_msg,
            )
        marker = out["message"]
        post_calls = [
            c for c in mfh.call_args_list if c.args[1] == "post_compact"
        ]
        self.assertEqual(len(post_calls), 1)
        ctx = post_calls[0].args[2]
        self.assertEqual(ctx["anchor_message"], marker.pk)
        self.assertEqual(ctx["boundary_pk"], e.pk)
