"""Regression tests for ``server.tasks.recovery_scheduler`` restart recovery.

Covers the gaps that left sessions stuck after a framework stop/restart:

* orphaned ACTIVE runs (dead worker, row stays ACTIVE forever),
* stale ACTIVE queries with a still-streaming response (must not be killed),
* rate-limit-parked turns (must not be mistaken for deadlocks).
"""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskRunStatus,
)
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from server.models.enums.task_enums import TaskExecutionMode
from server.models.enums.task_enums import TaskType


def _old(dt_field_minutes=20):
    return timezone.now() - timedelta(minutes=dt_field_minutes)


class RecoveryFixture(TestCase):
    def setUp(self):
        self.provider = ApiProvider.objects.create(name="rec-provider")
        self.model = AiModel.objects.create(
            api_provider=self.provider, name="RecModel", provider_model_id="rec"
        )
        self.agent = AgentModel.objects.create(name="rec-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = SessionModel.objects.create(name="rec-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=self.agent, pinned_agent_version=self.av
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="call_llm"),
            description="",
            function_schema={},
            task_type=TaskType.TASK,
            task_execution_mode=TaskExecutionMode.FUNCTION,
            requires_approval=False,
        )
        TaskDefinition.objects.filter(name="call_llm").update(
            latest_task_version=tdv
        )
        self.tdv = tdv
        self.ti = TaskInstance.objects.create(
            session=self.session,
            session_version=self.sv,
            task_definition_version=tdv,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
        )

    def _call(self, detail, status=TaskCallStatus.ACTIVE, age_min=20, **kw):
        call = AgentTaskCall.objects.create(
            session=self.session,
            session_version=self.sv,
            task_instance=self.ti,
            task_definition=self.tdv.task_definition,
            task_definition_version=self.tdv,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=status,
            status_detail=detail,
            **kw,
        )
        AgentTaskCall.objects.filter(pk=call.pk).update(
            updated_at=_old(age_min)
        )
        call.refresh_from_db()
        return call

    def _run(self, call, status=TaskRunStatus.ACTIVE, age_min=20):
        run = AgentTaskRun.objects.create(
            agent_task_call=call,
            task_instance=self.ti,
            task_definition_version=self.tdv,
            session=self.session,
            session_version=self.sv,
            requires_approval=False,
            time_limit=None,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            status=status,
        )
        AgentTaskRun.objects.filter(pk=run.pk).update(updated_at=_old(age_min))
        run.refresh_from_db()
        return run

    def _query(self, status=QueryStatus.ACTIVE, age_min=20):
        q = Query.objects.create(
            session=self.session, session_version=self.sv, status=status
        )
        Query.objects.filter(pk=q.pk).update(updated_at=_old(age_min))
        q.refresh_from_db()
        return q

    def _response(self, query, status=ResponseStatus.ACTIVE, age_min=20):
        r = Response.objects.create(
            query=query,
            session=self.session,
            session_version=self.sv,
            status=status,
        )
        Response.objects.filter(pk=r.pk).update(updated_at=_old(age_min))
        r.refresh_from_db()
        return r


class WorkerlessActiveRunTest(RecoveryFixture):
    def test_fails_orphaned_active_run_without_progress(self):
        """An ACTIVE run untouched for > timeout with no live response dies."""
        from server.tasks.recovery_scheduler import _recover_stuck_calls

        call = self._call(TaskCallStatusDetail.ACTIVE_RUNNING)
        run = self._run(call)
        _recover_stuck_calls()
        run.refresh_from_db()
        call.refresh_from_db()
        self.assertEqual(run.status, TaskRunStatus.FAILURE)
        self.assertEqual(call.status, TaskCallStatus.ENDED)

    def test_spares_active_run_with_live_response(self):
        """A recent ACTIVE response proves the worker is alive — hands off."""
        from server.tasks.recovery_scheduler import _recover_stuck_calls

        call = self._call(TaskCallStatusDetail.ACTIVE_RUNNING)
        run = self._run(call)
        query = self._query(status=QueryStatus.SUCCESS, age_min=20)
        self._response(query, status=ResponseStatus.ACTIVE, age_min=1)
        _recover_stuck_calls()
        run.refresh_from_db()
        call.refresh_from_db()
        self.assertEqual(run.status, TaskRunStatus.ACTIVE)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.ACTIVE_RUNNING)


class StaleQueryLivenessTest(RecoveryFixture):
    def test_skips_query_with_live_response(self):
        """Old ACTIVE query + recent ACTIVE response = healthy long stream."""
        from server.tasks.recovery_scheduler import _recover_stale_queries

        query = self._query(status=QueryStatus.ACTIVE, age_min=30)
        self._response(query, status=ResponseStatus.ACTIVE, age_min=1)
        with mock.patch(
            "runtime.events.publish_model_event"
        ):
            _recover_stale_queries()
        query.refresh_from_db()
        self.assertEqual(query.status, QueryStatus.ACTIVE)

    def test_resumes_query_with_stale_response(self):
        """Old ACTIVE query + stale response = dead worker, re-dispatch."""
        from server.tasks.recovery_scheduler import _recover_stale_queries

        query = self._query(status=QueryStatus.ACTIVE, age_min=30)
        self._response(query, status=ResponseStatus.ACTIVE, age_min=30)
        with mock.patch(
            "runtime.events.publish_model_event"
        ), mock.patch(
            "server.tasks.task_dispatcher._celery_run.delay"
        ):
            _recover_stale_queries()
        query.refresh_from_db()
        self.assertEqual(query.status, QueryStatus.WAITING)
        self.assertTrue(
            AgentTaskCall.objects.filter(
                session_version=self.sv,
                task_definition__name="call_llm",
            )
            .exclude(status=TaskCallStatus.ENDED)
            .exists()
        )


class RatelimitParkedTurnTest(RecoveryFixture):
    def test_spares_run_waiting_on_ratelimited_call(self):
        """A run parked on WAITING_RATELIMIT refs is live, not deadlocked."""
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        root = self._call(
            TaskCallStatusDetail.ACTIVE_RUNNING,
            status=TaskCallStatus.ACTIVE,
            age_min=60,
        )
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)
        root.refresh_from_db()

        parent = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            status=TaskCallStatus.WAITING,
            age_min=60,
        )
        AgentTaskCall.objects.filter(pk=parent.pk).update(session_root_task=root)
        run = self._run(
            parent, status=TaskRunStatus.WAITING_RESULTTASKS, age_min=60
        )

        parked = self._call(
            TaskCallStatusDetail.WAITING_RATELIMIT,
            status=TaskCallStatus.WAITING,
            age_min=5,
        )
        AgentTaskCall.objects.filter(pk=parked.pk).update(session_root_task=root)
        run.taskrun_result_references.add(parked)

        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        parked.refresh_from_db()
        self.assertEqual(run.status, TaskRunStatus.WAITING_RESULTTASKS)
        self.assertEqual(
            parked.status_detail, TaskCallStatusDetail.WAITING_RATELIMIT
        )


class CompactionForkRecoveryTest(RecoveryFixture):
    """A >30s compaction fork must never be force-failed as a deadlock.

    ``build_llm_compact_context`` returns the CHILD summarizer session's
    ``ingest_user_message`` call as its run result, so while the summarizer's
    ``call_llm`` is generating the parent chain looks quiet to the deadlock
    detector:

    * ``compact_turn`` run is WAITING_RESULTTASKS on its ``ingest_compaction``
      CHAIN step (WAITING_DEPENDENCY — no run yet, so the old walk stopped there
      and never reached the cross-session reference),
    * the ``build_llm_compact_context`` step is WAITING_RESULTTASKS on the child
      session's call (cross-session, invisible to the parent tree).

    The old walk ended without the child session's ACTIVE ``call_llm`` in
    ``root_task_ids``, so anything slower than the 30s grace got force-failed —
    killing the turn before the summarizer finished ("session never continues
    after a compaction").  The walk must descend through a ref's argument
    references to see the child tree.
    """

    def _child_session(self, name="compaction-fork"):
        sess = SessionModel.objects.create(name=name)
        sv = SessionVersionModel.objects.create(
            session=sess, agent=self.agent, pinned_agent_version=self.av
        )
        SessionModel.objects.filter(pk=sess.pk).update(latest_session_version=sv)
        return sess, sv

    def test_spares_turn_while_summarizing_cross_session(self):
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        root = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            status=TaskCallStatus.WAITING,
            age_min=1,
        )
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)
        root.refresh_from_db()

        # compact_turn CHAIN run waiting on its ingest_compaction step.
        chain_call = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            status=TaskCallStatus.WAITING,
            age_min=60,
        )
        AgentTaskCall.objects.filter(pk=chain_call.pk).update(
            session_root_task=root
        )
        chain_run = self._run(
            chain_call, status=TaskRunStatus.WAITING_RESULTTASKS, age_min=60
        )

        # ingest_compaction CHAIN step — WAITING_DEPENDENCY on its build arg.
        ingest = self._call(
            TaskCallStatusDetail.WAITING_DEPENDENCY,
            status=TaskCallStatus.WAITING,
            age_min=60,
        )
        AgentTaskCall.objects.filter(pk=ingest.pk).update(session_root_task=root)
        chain_run.taskrun_result_references.add(ingest)

        # build_llm_compact_context step — WAITING cross-session on the child.
        build = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            status=TaskCallStatus.WAITING,
            age_min=60,
        )
        AgentTaskCall.objects.filter(pk=build.pk).update(session_root_task=root)
        ingest.taskcall_arg_references.add(build)
        build_run = self._run(
            build, status=TaskRunStatus.WAITING_RESULTTASKS, age_min=60
        )

        # The child summarizer session is genuinely working — its root call and
        # call_llm are ACTIVE_RUNNING past the grace period.
        child_sess, child_sv = self._child_session()
        kw_defaults = dict(
            task_instance=self.ti,
            task_definition=self.tdv.task_definition,
            task_definition_version=self.tdv,
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
        )
        child_root = AgentTaskCall.objects.create(
            session=child_sess,
            session_version=child_sv,
            status=TaskCallStatus.ACTIVE,
            status_detail=TaskCallStatusDetail.ACTIVE_RUNNING,
            **kw_defaults,
        )
        AgentTaskCall.objects.filter(pk=child_root.pk).update(
            session_root_task=child_root, updated_at=_old(60)
        )
        child_root.refresh_from_db()
        child_ingest = AgentTaskCall.objects.create(
            session=child_sess,
            session_version=child_sv,
            status=TaskCallStatus.ACTIVE,
            status_detail=TaskCallStatusDetail.ACTIVE_RUNNING,
            **kw_defaults,
        )
        AgentTaskCall.objects.filter(pk=child_ingest.pk).update(
            session_root_task=child_root, updated_at=_old(60)
        )
        child_ingest.refresh_from_db()
        build_run.taskrun_result_references.add(child_ingest)

        _resolve_stuck_waiting_runs()

        chain_run.refresh_from_db()
        build_run.refresh_from_db()
        self.assertEqual(chain_run.status, TaskRunStatus.WAITING_RESULTTASKS)
        self.assertEqual(build_run.status, TaskRunStatus.WAITING_RESULTTASKS)


class SessionFifoTest(RecoveryFixture):
    """Parked ingests must start strictly FIFO — one live turn per session.

    Releasing every WAITING_QUEUE ingest at once runs turns concurrently and
    the losers die on the duplicate-query guard in ``build_llm_context``.
    """

    def _ingest_call(self, detail, status, age_min=5):
        ingest_tdv = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="ingest_user_message"),
            description="",
            function_schema={},
            task_type=TaskType.TASK,
            task_execution_mode=TaskExecutionMode.CHAIN,
            requires_approval=False,
        )
        call = self._call(detail, status=status, age_min=age_min)
        AgentTaskCall.objects.filter(pk=call.pk).update(
            task_definition=ingest_tdv.task_definition,
            task_definition_version=ingest_tdv,
        )
        call.refresh_from_db()
        return call

    def test_blocked_while_turn_live(self):
        from runtime.tasks.call_scheduler import CallScheduler

        live = self._ingest_call(
            TaskCallStatusDetail.ACTIVE_RUNNING,
            status=TaskCallStatus.ACTIVE,
        )
        parked = self._ingest_call(
            TaskCallStatusDetail.WAITING_QUEUE,
            status=TaskCallStatus.WAITING,
        )
        self.assertTrue(CallScheduler._session_queue_blocked(parked))
        live.refresh_from_db()

    def test_blocked_behind_older_parked_message(self):
        from runtime.tasks.call_scheduler import CallScheduler

        older = self._ingest_call(
            TaskCallStatusDetail.WAITING_QUEUE,
            status=TaskCallStatus.WAITING,
            age_min=6,
        )
        newer = self._ingest_call(
            TaskCallStatusDetail.WAITING_QUEUE,
            status=TaskCallStatus.WAITING,
            age_min=5,
        )
        self.assertFalse(CallScheduler._session_queue_blocked(older))
        self.assertTrue(CallScheduler._session_queue_blocked(newer))

    def test_free_for_non_ingest_calls(self):
        from runtime.tasks.call_scheduler import CallScheduler

        live = self._ingest_call(
            TaskCallStatusDetail.ACTIVE_RUNNING,
            status=TaskCallStatus.ACTIVE,
        )
        # A parallel-limit-parked tool call is not turn-ordered.
        tool_call = self._call(
            TaskCallStatusDetail.WAITING_QUEUE, status=TaskCallStatus.WAITING
        )
        self.assertFalse(CallScheduler._session_queue_blocked(tool_call))
        live.refresh_from_db()

    def test_tick_leaves_parked_ingest_alone_while_turn_live(self):
        from server.tasks.tick_scheduler import _release_queued_calls

        self._ingest_call(
            TaskCallStatusDetail.ACTIVE_RUNNING,
            status=TaskCallStatus.ACTIVE,
        )
        parked = self._ingest_call(
            TaskCallStatusDetail.WAITING_QUEUE,
            status=TaskCallStatus.WAITING,
        )
        runs_before = AgentTaskRun.objects.filter(
            agent_task_call=parked
        ).count()
        _release_queued_calls()
        parked.refresh_from_db()
        self.assertEqual(
            parked.status_detail, TaskCallStatusDetail.WAITING_QUEUE
        )
        self.assertEqual(
            AgentTaskRun.objects.filter(agent_task_call=parked).count(),
            runs_before,
        )


class InterruptPropagationTest(RecoveryFixture):
    """Interrupting a running ingest must unblock its waiting parents."""

    def test_stop_propagates_to_waiting_parent(self):
        from runtime.session.session import Session

        ingest_tdv = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(
                name="ingest_user_message"
            ),
            description="",
            function_schema={},
            task_type=TaskType.TASK,
            task_execution_mode=TaskExecutionMode.CHAIN,
            requires_approval=False,
        )
        running = self._call(
            TaskCallStatusDetail.ACTIVE_RUNNING, status=TaskCallStatus.ACTIVE
        )
        AgentTaskCall.objects.filter(pk=running.pk).update(
            task_definition=ingest_tdv.task_definition,
            task_definition_version=ingest_tdv,
        )
        parent_call = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            status=TaskCallStatus.WAITING,
        )
        parent_run = self._run(
            parent_call, status=TaskRunStatus.WAITING_RESULTTASKS
        )
        parent_run.taskrun_result_references.add(running)

        Session(session_model=self.session).stop_generation()

        running.refresh_from_db()
        parent_run.refresh_from_db()
        # ACTIVE_RUNNING has no FSM path to ENDED_STOPPED — the tree cancel
        # fails it, which still unblocks waiting parents.
        self.assertEqual(
            running.status_detail, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )
        self.assertEqual(parent_run.status, TaskRunStatus.FAILURE)


class RunFsmExtrasTest(RecoveryFixture):
    def test_succeed_keeps_ended_at_and_extra_on_waiting_path(self):
        from runtime.tasks.run_fsm import TaskRunStateMachine

        call = self._call(TaskCallStatusDetail.ACTIVE_RUNNING)
        run = self._run(call, status=TaskRunStatus.WAITING_RESULTTASKS)
        self.assertTrue(
            TaskRunStateMachine.succeed(
                run.pk, extra={"result_json": {"ok": True}}
            )
        )
        run.refresh_from_db()
        self.assertEqual(run.status, TaskRunStatus.SUCCESS)
        self.assertIsNotNone(run.ended_at)
        self.assertEqual(run.result_json, {"ok": True})
