"""Regression tests for call retries, including waiting-state failures.

Covers the incident where a healthy ``process_summary`` run was failed
while waiting on its ``double_check_summary`` sub-call and the parent
``update_timeline`` toolcall died with ``ENDED_FAILURE_EXCEPTION`` even
though retries were conceptually available:

* an ACTIVE run failure retries when budget remains (existing behavior),
* a WAITING_RESULTTASKS run failure retries when all result refs ended
  (new: ``WAITING_SUBTASKS_OR_HOOKS`` → ``WAITING_RETRY``),
* a WAITING run failure does NOT retry while a result ref is still live
  (re-executing would fork duplicate sub-calls),
* no retry once the budget is exhausted.
"""
from __future__ import annotations

from django.test import TestCase

from runtime.tasks.call_fsm import TaskCallStateMachine
from runtime.tasks.call_scheduler import CallScheduler
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskExecutionMode,
    TaskType,
)
from server.models.enums.task_enums import TaskRunStatus
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance


class RetryFixture(TestCase):
    def setUp(self):
        agent = AgentModel.objects.create(name="retry-agent")
        av = AgentVersionModel.objects.create(
            agent=agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = SessionModel.objects.create(name="retry-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=agent, pinned_agent_version=av
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=TaskDefinition.objects.create(name="retry-task"),
            description="",
            function_schema={},
            task_type=TaskType.TASK,
            task_execution_mode=TaskExecutionMode.FUNCTION,
            requires_approval=False,
        )
        TaskDefinition.objects.filter(name="retry-task").update(
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
            max_retries=2,
            retry_delay=0,
            retry_requires_approval=False,
        )

    def _call(self, detail, status, max_retries=2):
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
            max_retries=max_retries,
            retry_delay=0,
            retry_requires_approval=False,
            status=status,
            status_detail=detail,
        )
        call.refresh_from_db()
        return call

    def _run(self, call, status):
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
        run.refresh_from_db()
        return run


class ActiveRetryTest(RetryFixture):
    def test_active_run_failure_retries_when_budget_remains(self):
        """Existing behavior: ACTIVE failure parks the call in WAITING_RETRY."""
        call = self._call(TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatus.ACTIVE)
        run = self._run(call, TaskRunStatus.FAILURE)
        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
        call.refresh_from_db()
        self.assertEqual(call.status, TaskCallStatus.WAITING)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_RETRY)
        self.assertEqual(call.retry_count, 1)

    def test_active_run_failure_fails_when_budget_exhausted(self):
        """max_retries=0 keeps the old immediate-failure behavior."""
        call = self._call(
            TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatus.ACTIVE, max_retries=0
        )
        run = self._run(call, TaskRunStatus.FAILURE)
        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
        call.refresh_from_db()
        self.assertEqual(call.status, TaskCallStatus.ENDED)
        self.assertEqual(
            call.status_detail, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )
        self.assertEqual(call.retry_count, 0)


class WaitingRetryTest(RetryFixture):
    def _waiting_call_with_ref(self, ref_detail, ref_status, max_retries=2):
        call = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            TaskCallStatus.WAITING,
            max_retries=max_retries,
        )
        run = self._run(call, TaskRunStatus.FAILURE)
        # The run had entered WAITING_RESULTTASKS on this ref before failing.
        ref = self._call(ref_detail, ref_status)
        run.taskrun_result_references.add(ref)
        return call, run, ref

    def test_waiting_run_failure_retries_when_refs_ended(self):
        """A waiting run whose refs all ended retries instead of dying."""
        call, run, _ref = self._waiting_call_with_ref(
            TaskCallStatusDetail.ENDED_SUCCESS, TaskCallStatus.ENDED
        )
        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
        call.refresh_from_db()
        self.assertEqual(call.status, TaskCallStatus.WAITING)
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_RETRY)
        self.assertEqual(call.retry_count, 1)

    def test_waiting_run_failure_no_retry_when_ref_live(self):
        """A waiting run with a still-running ref fails without retrying.

        Re-executing the function would re-dispatch sub-calls and fork
        duplicates of the live child.
        """
        call, run, _ref = self._waiting_call_with_ref(
            TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatus.ACTIVE
        )
        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
        call.refresh_from_db()
        self.assertEqual(call.status, TaskCallStatus.ENDED)
        self.assertEqual(
            call.status_detail, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )
        self.assertEqual(call.retry_count, 0)

    def test_waiting_run_failure_fails_when_budget_exhausted(self):
        """max_retries=0 on a waiting call keeps immediate failure."""
        call, run, _ref = self._waiting_call_with_ref(
            TaskCallStatusDetail.ENDED_SUCCESS, TaskCallStatus.ENDED, max_retries=0
        )
        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
        call.refresh_from_db()
        self.assertEqual(call.status, TaskCallStatus.ENDED)
        self.assertEqual(
            call.status_detail, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )


class ScheduleRetryFsmTest(RetryFixture):
    def test_schedule_retry_from_waiting_subtasks(self):
        """FSM accepts WAITING_SUBTASKS_OR_HOOKS → WAITING_RETRY."""
        call = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS, TaskCallStatus.WAITING
        )
        self.assertTrue(TaskCallStateMachine.schedule_retry(call.pk, 0, 2))
        call.refresh_from_db()
        self.assertEqual(call.status_detail, TaskCallStatusDetail.WAITING_RETRY)
        self.assertEqual(call.retry_count, 1)

    def test_schedule_retry_respects_budget(self):
        """retry_count >= max_retries refuses the transition."""
        call = self._call(
            TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            TaskCallStatus.WAITING,
            max_retries=1,
        )
        AgentTaskCall.objects.filter(pk=call.pk).update(retry_count=1)
        self.assertFalse(TaskCallStateMachine.schedule_retry(call.pk, 0, 1))
        call.refresh_from_db()
        self.assertEqual(
            call.status_detail, TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS
        )
