import pytest
from unittest.mock import patch

from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus, TaskType


@pytest.mark.django_db
class TestTaskCalls:
    def test_list_task_calls(self, auth_client):
        resp = auth_client.get('/api/v1/task-calls/')
        assert resp.status_code == 200

    def test_get_task_call_detail(self, auth_client):
        agent = AgentModel.objects.create(name='tc-agent')
        session = SessionModel.objects.create(name='tc-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='test-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.COMMAND,
            description='test', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status_detail=TaskCallStatusDetail.NEW,
        )
        resp = auth_client.get(f'/api/v1/task-calls/{call.id}/')
        assert resp.status_code == 200
        assert 'runs' in resp.data

    def test_task_call_filter_by_session(self, auth_client):
        resp = auth_client.get('/api/v1/task-calls/?session=99999')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTaskCallApproval:
    """Tests for the approve/deny endpoints on TaskCallViewSet."""

    def _make_halted_call(self, auth_client) -> AgentTaskCall:
        agent = AgentModel.objects.create(name='approval-agent')
        session = SessionModel.objects.create(name='approval-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='approval-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='test', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=True, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=True,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.HALTED,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        )
        return call

    def test_approve_halted_call(self, auth_client):
        call = self._make_halted_call(auth_client)
        resp = auth_client.post(f'/api/v1/task-calls/{call.id}/approve/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'approved'

    def test_deny_halted_call(self, auth_client):
        call = self._make_halted_call(auth_client)
        resp = auth_client.post(f'/api/v1/task-calls/{call.id}/deny/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'denied'

    def test_approve_non_halted_call_returns_409(self, auth_client):
        agent = AgentModel.objects.create(name='approval-agent2')
        session = SessionModel.objects.create(name='approval-session2')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='approval-task2')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='test', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status_detail=TaskCallStatusDetail.NEW,
        )
        resp = auth_client.post(f'/api/v1/task-calls/{call.id}/approve/')
        assert resp.status_code == 409
        assert 'not awaiting approval' in resp.data['error'].lower()

    def test_deny_non_halted_call_returns_409(self, auth_client):
        agent = AgentModel.objects.create(name='approval-agent3')
        session = SessionModel.objects.create(name='approval-session3')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='approval-task3')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='test', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status_detail=TaskCallStatusDetail.NEW,
        )
        resp = auth_client.post(f'/api/v1/task-calls/{call.id}/deny/')
        assert resp.status_code == 409
        assert 'not awaiting approval' in resp.data['error'].lower()


@pytest.mark.django_db
class TestCallSchedulerGuardrails:
    """Tests for CallScheduler._guardrail_shell_check / _guardrail_python_check."""

    def _make_taskcall(self, task_name="shell", source=None, cargs=None,
                       iargs=None, requires_approval=False,
                       status_detail=None):
        agent = AgentModel.objects.create(name='gs-agent')
        session = SessionModel.objects.create(name='gs-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name=task_name)
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description=task_name, function_schema={},
        )
        iargs_json = {"*": iargs} if iargs else {}
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=requires_approval, priority=0, max_retries=0,
            retry_delay=0, retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
            iarguments_json=iargs_json,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json=cargs or {}, requires_approval=requires_approval,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status_detail=status_detail or TaskCallStatusDetail.WAITING_DEPENDENCY,
        )
        return call

    # --- Shell guardrail ---

    def test_shell_guardrail_dangerous_marked(self, db):
        """Dangerous shell command → requires_approval=True + reason stored."""
        call = self._make_taskcall(
            task_name="shell", source="rm -rf /", cargs={"source": "rm -rf /"},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        assert call.guardrail_reason is not None

    def test_shell_guardrail_safe_not_marked(self, db):
        """Safe shell command → no change."""
        call = self._make_taskcall(
            task_name="shell", source="ls -la", cargs={"source": "ls -la"},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_shell_guardrail_skips_non_shell_task(self, db):
        """Non-shell task name → guardrail skipped."""
        call = self._make_taskcall(
            task_name="git", source="rm -rf /", cargs={"source": "rm -rf /"},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_shell_guardrail_empty_source_noop(self, db):
        """Empty source → no crash, no change."""
        call = self._make_taskcall(
            task_name="shell", source="", cargs={},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_shell_guardrail_source_from_positional_args(self, db):
        """Source extracted from *args when no 'source' key."""
        call = self._make_taskcall(
            task_name="shell", source="rm -rf /",
            cargs={"*": ["rm -rf /"]},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        assert call.guardrail_reason is not None

    def test_shell_guardrail_source_from_instance_defaults(self, db):
        """Source extracted from instance iarguments_json when call args empty."""
        call = self._make_taskcall(
            task_name="shell", source="rm -rf /",
            cargs={}, iargs=["rm -rf /"],
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True

    def test_shell_guardrail_already_approved_skipped(self, db):
        """If requires_approval already True, guardrail skips entirely."""
        call = self._make_taskcall(
            task_name="shell", source="rm -rf /", cargs={"source": "rm -rf /"},
            requires_approval=True,
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_shell_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        # Guardrail should not modify carguments when already requires_approval
        assert call.guardrail_reason is not None

    # --- Python guardrail ---

    def test_python_guardrail_dangerous_marked(self, db):
        """Dangerous Python code → requires_approval=True + reason stored."""
        call = self._make_taskcall(
            task_name="python", source='import os; os.system("ls")',
            cargs={"source": 'import os; os.system("ls")'},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_python_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True
        assert call.guardrail_reason is not None

    def test_python_guardrail_safe_not_marked(self, db):
        """Safe Python code → no change."""
        call = self._make_taskcall(
            task_name="python", source='print("hello")',
            cargs={"source": 'print("hello")'},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_python_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_python_guardrail_skips_non_python_task(self, db):
        """Non-python task name → guardrail skipped."""
        call = self._make_taskcall(
            task_name="git", source='import os; os.system("ls")',
            cargs={"source": 'import os; os.system("ls")'},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_python_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_python_guardrail_empty_source_noop(self, db):
        """Empty Python source → no crash, no change."""
        call = self._make_taskcall(
            task_name="python", source="", cargs={},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_python_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is False

    def test_python_guardrail_source_from_positional_args(self, db):
        """Python source extracted from *args when no 'source' key."""
        call = self._make_taskcall(
            task_name="python", source='import os; os.system("ls")',
            cargs={"*": ['import os; os.system("ls")']},
        )
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler._guardrail_python_check(call.pk)
        call.refresh_from_db()
        assert call.requires_approval is True


@pytest.mark.django_db
class TestGuardrailFullFlow:
    """Integration test: pre-schedule guardrail → halt → approve → enqueue."""

    def _make_waiting_dependency_call(self, task_name, source):
        agent = AgentModel.objects.create(name='gff-agent')
        session = SessionModel.objects.create(name='gff-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name=task_name)
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description=task_name, function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        call = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={"source": source}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        )
        return call

    def test_guardrail_pre_schedule_shell_halt_and_approve(self, db):
        """Shell: pre-schedule → HALTED_APPROVAL → approve → WAITING_QUEUE."""
        from runtime.tasks.call_scheduler import CallScheduler
        from runtime.tasks.call_fsm import TaskCallStateMachine

        call = self._make_waiting_dependency_call("shell", "rm -rf /")

        CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
        assert call.requires_approval is True
        assert call.guardrail_reason is not None

        approved = TaskCallStateMachine.approve(call.pk)
        assert approved is True
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.WAITING_QUEUE
        assert call.is_approved is True

    def test_guardrail_pre_schedule_shell_safe_enqueues_directly(self, db):
        """Shell: safe command → enqueues without halt."""
        from runtime.tasks.call_scheduler import CallScheduler

        call = self._make_waiting_dependency_call("shell", "ls -la")

        # start_new_taskrun would fail without full agent setup, so mock it
        with patch.object(CallScheduler, 'start_new_taskrun') as mock_start:
            CallScheduler.on_all_arg_reference_tasks_ended(call.pk)

        call.refresh_from_db()
        # Safe command → no halt
        assert call.status_detail != TaskCallStatusDetail.HALTED_APPROVAL
        assert call.status_detail == TaskCallStatusDetail.WAITING_QUEUE
        mock_start.assert_called_once_with(call.pk)

    def test_guardrail_pre_schedule_python_halt_and_approve(self, db):
        """Python: pre-schedule → HALTED_APPROVAL → approve → WAITING_QUEUE."""
        from runtime.tasks.call_scheduler import CallScheduler
        from runtime.tasks.call_fsm import TaskCallStateMachine

        call = self._make_waiting_dependency_call(
            "python", 'import os; os.system("ls")',
        )

        CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
        assert call.requires_approval is True

        approved = TaskCallStateMachine.approve(call.pk)
        assert approved is True
        call.refresh_from_db()
        assert call.status_detail == TaskCallStatusDetail.WAITING_QUEUE
        assert call.is_approved is True


@pytest.mark.django_db
class TestTaskRuns:
    def test_list_task_runs(self, auth_client):
        resp = auth_client.get('/api/v1/task-runs/')
        assert resp.status_code == 200

    def test_get_task_run_detail(self, auth_client):
        agent = AgentModel.objects.create(name='tr-agent')
        session = SessionModel.objects.create(name='tr-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='tr-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.COMMAND,
            description='test', function_schema={},
        )
        call = AgentTaskCall.objects.create(
            session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            status_detail=TaskCallStatusDetail.NEW,
        )
        run = AgentTaskRun.objects.create(
            agent_task_call=call, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.NEW,
        )
        resp = auth_client.get(f'/api/v1/task-runs/{run.id}/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestParallelRunLimit:
    """Regression test for the I1 violation risk: concurrent dispatches for
    two calls on the same task_instance must not both create runs when the
    per-instance parallel limit would be exceeded."""

    def _make_setup(self):
        agent = AgentModel.objects.create(name='i1-agent')
        session = SessionModel.objects.create(name='i1-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='i1-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='i1-task', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        return session, sv, td, tdv, ti

    def _make_queued_call(self, ti, td, tdv, session, sv, parent_run=None, root=None):
        return AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            parent_taskrun=parent_run,
            session_root_task=root,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        )

    def test_second_dispatch_blocked_when_limit_reached(self, db):
        """A second call on a full task_instance must not get a new run."""
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()
        call1 = self._make_queued_call(ti, td, tdv, session, sv)
        call2 = self._make_queued_call(ti, td, tdv, session, sv)

        # call1 already holds the single run slot (limit=1).
        AgentTaskRun.objects.create(
            agent_task_call=call1, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.QUEUED,
        )

        with patch.object(CallScheduler, '_pick_up_and_create_run', return_value=None) as mock:
            CallScheduler.start_new_taskrun(call2.pk)

        mock.assert_not_called()
        call2.refresh_from_db()
        assert call2.status_detail == TaskCallStatusDetail.WAITING_QUEUE

    def test_second_dispatch_proceeds_when_slot_free(self, db):
        """With no runs yet, the first dispatch does create a run."""
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()
        call = self._make_queued_call(ti, td, tdv, session, sv)

        with patch.object(CallScheduler, '_pick_up_and_create_run', return_value=None) as mock:
            CallScheduler.start_new_taskrun(call.pk)

        mock.assert_called_once_with(call.pk)

    def test_continuation_descendant_not_blocked_by_ancestor(self, db):
        """A same-turn continuation (decide_next_step dispatching the next
        process_turn) is a descendant of the run holding the TI slot.  It must
        NOT be blocked, or the agent loop deadlocks against its own parent (E5).

        Regression for commit 0182d96, which started enforcing the per-TI
        limiter in ``start_new_taskrun``: the counter counted *every* active
        run on the task_instance, including the ancestor process_turn's run
        that spawned the continuation via its tail (decide_next_step)."""
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()

        # Old process_turn (chain) already holds the single slot.
        old = self._make_queued_call(ti, td, tdv, session, sv)
        old_run = AgentTaskRun.objects.create(
            agent_task_call=old, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )

        # decide_next_step is a child of old process_turn's run.
        next_step = self._make_queued_call(
            ti, td, tdv, session, sv, parent_run=old_run, root=old,
        )
        next_step_run = AgentTaskRun.objects.create(
            agent_task_call=next_step, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )

        # New process_turn dispatched by decide_next_step — descendant of old.
        cont = self._make_queued_call(
            ti, td, tdv, session, sv, parent_run=next_step_run, root=old,
        )

        with patch.object(CallScheduler, '_pick_up_and_create_run', return_value=None) as mock:
            CallScheduler.start_new_taskrun(cont.pk)

        # The continuation must be admitted despite the ancestor holding the slot.
        mock.assert_called_once_with(cont.pk)

    def test_unrelated_sibling_still_blocked_when_limit_reached(self, db):
        """A call that is NOT a descendant of the slot holder is a genuinely
        independent turn (e.g. a second user message) and must remain blocked."""
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()
        call1 = self._make_queued_call(ti, td, tdv, session, sv, root=None)
        call1 = AgentTaskCall.objects.get(pk=call1.pk)
        AgentTaskRun.objects.create(
            agent_task_call=call1, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.QUEUED,
        )
        # Independent second call — different root, no ancestor link.
        call2 = self._make_queued_call(ti, td, tdv, session, sv, root=None)

        with patch.object(CallScheduler, '_pick_up_and_create_run', return_value=None) as mock:
            CallScheduler.start_new_taskrun(call2.pk)

        mock.assert_not_called()
        call2.refresh_from_db()
        assert call2.status_detail == TaskCallStatusDetail.WAITING_QUEUE


@pytest.mark.django_db
class TestRecoverStuckCalls:
    """Recovery-pass handling of zombie calls.

    A call whose root task has ended can never start: ``start_running``
    rejects ``ACTIVE_QUEUED → ACTIVE_RUNNING`` once the root turn is done.
    The recovery pass must cancel such calls instead of endlessly
    re-dispatching their QUEUED runs.
    """

    def _make_setup(self):
        agent = AgentModel.objects.create(name='recover-agent')
        session = SessionModel.objects.create(name='recover-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='recover-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='recover-task', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        return session, sv, td, tdv, ti

    def _make_call(self, ti, td, tdv, session, sv, *, root=None):
        return AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            session_root_task=root,
            status=TaskCallStatus.ACTIVE,
            status_detail=TaskCallStatusDetail.ACTIVE_QUEUED,
        )

    def test_zombie_call_with_ended_root_is_cancelled(self, db):
        """ACTIVE_QUEUED call whose root ended → cancelled, run failed, no redispatch."""
        from server.tasks.recovery_scheduler import _recover_stuck_calls

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None)
        AgentTaskCall.objects.filter(pk=root.pk).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
            ended_at=None,
        )
        root.refresh_from_db()

        zombie = self._make_call(ti, td, tdv, session, sv, root=root)
        AgentTaskRun.objects.create(
            agent_task_call=zombie, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.QUEUED,
        )

        with patch('server.tasks.task_dispatcher.celery_delay') as mock_dispatch:
            _recover_stuck_calls()

        zombie.refresh_from_db()
        assert zombie.status == TaskCallStatus.ENDED
        assert zombie.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
        run = zombie.related_agent_task_runs.first()
        assert run.status == TaskRunStatus.FAILURE
        mock_dispatch.assert_not_called()

    def test_zombie_call_with_no_run_is_cancelled(self, db):
        """ACTIVE_QUEUED call (no run) with ended root → cancelled, not re-queued."""
        from server.tasks.recovery_scheduler import _recover_stuck_calls

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None)
        AgentTaskCall.objects.filter(pk=root.pk).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
            ended_at=None,
        )
        root.refresh_from_db()

        zombie = self._make_call(ti, td, tdv, session, sv, root=root)

        with patch('server.tasks.task_dispatcher.celery_delay') as mock_dispatch:
            _recover_stuck_calls()

        zombie.refresh_from_db()
        assert zombie.status == TaskCallStatus.ENDED
        assert zombie.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
        mock_dispatch.assert_not_called()

    def test_orphan_call_with_live_root_is_requeued(self, db):
        """ACTIVE_QUEUED call with a live root and no run → re-queued normally."""
        from server.tasks.recovery_scheduler import _recover_stuck_calls
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None)
        AgentTaskRun.objects.create(
            agent_task_call=root, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.ACTIVE,
        )
        orphan = self._make_call(ti, td, tdv, session, sv, root=root)

        with patch.object(CallScheduler, 'start_new_taskrun') as mock_start, \
             patch('server.tasks.task_dispatcher.celery_delay') as mock_dispatch:
            _recover_stuck_calls()

        orphan.refresh_from_db()
        assert orphan.status_detail == TaskCallStatusDetail.WAITING_QUEUE
        mock_start.assert_called_with(orphan.pk)
        mock_dispatch.assert_not_called()

    def test_waiting_queue_call_with_dangling_ref_is_cancelled(self, db):
        """WAITING_QUEUE call referencing a deleted call → cancelled, not released."""
        from server.tasks.recovery_scheduler import _release_queued_calls
        from runtime.tasks.call_scheduler import CallScheduler

        session, sv, td, tdv, ti = self._make_setup()

        # Root call for session_root_task self-reference is unnecessary here; a
        # plain WAITING_QUEUE call whose args reference a non-existent call.
        ghost = AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={"_type": "AgentTaskCall", "pk": 999999},
            requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            session_root_task=None,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        )

        with patch.object(CallScheduler, 'start_new_taskrun') as mock_start:
            _release_queued_calls()

        ghost.refresh_from_db()
        assert ghost.status == TaskCallStatus.ENDED
        assert ghost.status_detail == TaskCallStatusDetail.ENDED_CANCELLED
        mock_start.assert_not_called()


@pytest.mark.django_db
class TestResolveStuckWaitingRuns:
    """Deadlock-breaker safety: must not fail runs whose tree is still alive."""

    def _make_setup(self):
        agent = AgentModel.objects.create(name='stuck-agent')
        session = SessionModel.objects.create(name='stuck-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        td = TaskDefinition.objects.create(name='stuck-task')
        tdv = TaskDefinitionVersion.objects.create(
            task_definition=td, task_type=TaskType.TOOL,
            description='stuck-task', function_schema={},
        )
        ti = TaskInstance.objects.create(
            task_definition_version=tdv, session=session, session_version=sv,
            requires_approval=False, priority=0, max_retries=0, retry_delay=0,
            retry_requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, time_limit=None,
        )
        return session, sv, td, tdv, ti

    def _make_call(self, ti, td, tdv, session, sv, *, root, detail):
        return AgentTaskCall.objects.create(
            task_definition=td, task_definition_version=tdv,
            task_instance=ti, session=session, session_version=sv,
            carguments_json={}, requires_approval=False,
            max_subtask_errors=0, max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0, limit_per_instance_parallel_runs=1,
            max_retries=0, retry_delay=0, retry_requires_approval=False,
            session_root_task=root,
            status=TaskCallStatus.WAITING,
            status_detail=detail,
        )

    def test_run_with_live_tree_not_failed(self, db):
        """WAITING_RESULTTASKS run whose ref is WAITING_DEPENDENCY but a sibling
        call is ACTIVE_RUNNING → NOT failed (healthy-but-slow chain)."""
        from datetime import timedelta
        from django.utils import timezone
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None,
                               detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)

        # The chain parent: WAITING_RESULTTASKS run waiting on a ref.
        parent = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        run = AgentTaskRun.objects.create(
            agent_task_call=parent, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        # Force updated_at older than the 30s grace.
        AgentTaskRun.objects.filter(pk=run.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        # The pending ref: still waiting on its own deps (WAITING_DEPENDENCY).
        ref = self._make_call(ti, td, tdv, session, sv, root=root,
                              detail=TaskCallStatusDetail.WAITING_DEPENDENCY)
        run.taskrun_result_references.add(ref)

        # A sibling in the root tree is genuinely ACTIVE_RUNNING (slow call_llm)
        # with its run in ACTIVE (doing real work), not WAITING_RESULTTASKS.
        sibling = self._make_call(ti, td, tdv, session, sv, root=root,
                                  detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        AgentTaskRun.objects.create(
            agent_task_call=sibling, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.ACTIVE,
        )

        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        assert run.status == TaskRunStatus.WAITING_RESULTTASKS

    def test_run_with_halted_approval_ref_is_not_failed(self, db):
        """A WAITING_RESULTTASKS run whose pending ref is HALTED_APPROVAL is
        paused on a human decision, not deadlocked — it must NOT be force-failed.
        (Regression: whole chains died ~8s after a python call went to approval
        because HALTED_APPROVAL was treated as a non-progressing state.)"""
        from datetime import timedelta
        from django.utils import timezone
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None,
                               detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)

        parent = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        run = AgentTaskRun.objects.create(
            agent_task_call=parent, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        AgentTaskRun.objects.filter(pk=run.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        # The pending ref is halted for human approval (python guardrail).
        ref = self._make_call(ti, td, tdv, session, sv, root=root,
                              detail=TaskCallStatusDetail.HALTED_APPROVAL)
        run.taskrun_result_references.add(ref)

        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        assert run.status == TaskRunStatus.WAITING_RESULTTASKS

    def test_run_with_dead_tree_is_failed(self, db):
        """WAITING_RESULTTASKS run whose whole tree is stuck → failed (true deadlock)."""
        from datetime import timedelta
        from django.utils import timezone
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None,
                               detail=TaskCallStatusDetail.WAITING_QUEUE)
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)

        parent = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.WAITING_QUEUE)
        run = AgentTaskRun.objects.create(
            agent_task_call=parent, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        AgentTaskRun.objects.filter(pk=run.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )
        ref = self._make_call(ti, td, tdv, session, sv, root=root,
                              detail=TaskCallStatusDetail.WAITING_DEPENDENCY)
        run.taskrun_result_references.add(ref)

        # No sibling is active — the whole tree is stuck.
        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        assert run.status == TaskRunStatus.FAILURE

    def test_run_with_parked_ref_and_ready_dependency_not_failed(self, db):
        """A WAITING_RESULTTASKS run whose pending ref is parked in
        WAITING_SUBTASKS_OR_HOOKS, while a sibling chain step is
        WAITING_DEPENDENCY with all its deps ended, is mid-chain — NOT failed.
        (Regression: session-963 — a healthy chain was force-failed in the gap
        between the previous step ending and the next step being released.)"""
        from datetime import timedelta
        from django.utils import timezone
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None,
                               detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS)
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)

        parent = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS)
        run = AgentTaskRun.objects.create(
            agent_task_call=parent, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        AgentTaskRun.objects.filter(pk=run.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )

        # The pending ref is itself a parked chain parent (WAITING_SUBTASKS_OR_HOOKS):
        # its run waits on the chain steps below it.
        parked = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS)
        parked_run = AgentTaskRun.objects.create(
            agent_task_call=parked, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        run.taskrun_result_references.add(parked)

        # Previous chain step just ended; the next step is WAITING_DEPENDENCY
        # with all its deps (prev) ended — about to be released by the Celery
        # on_arg_reference_task_ended notification.
        prev = self._make_call(ti, td, tdv, session, sv, root=root,
                               detail=TaskCallStatusDetail.ENDED_SUCCESS)
        AgentTaskCall.objects.filter(pk=prev.pk).update(status=TaskCallStatus.ENDED)
        nxt = self._make_call(ti, td, tdv, session, sv, root=root,
                              detail=TaskCallStatusDetail.WAITING_DEPENDENCY)
        nxt.taskcall_arg_references.add(prev)
        parked_run.taskrun_result_references.add(nxt)

        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        assert run.status == TaskRunStatus.WAITING_RESULTTASKS

    def test_run_with_blocked_active_sibling_is_failed(self, db):
        """An ACTIVE_RUNNING sibling whose own run is WAITING_RESULTTASKS is itself
        blocked (E5 circular deadlock) — it must NOT protect the tree."""
        from datetime import timedelta
        from django.utils import timezone
        from server.tasks.recovery_scheduler import _resolve_stuck_waiting_runs

        session, sv, td, tdv, ti = self._make_setup()

        root = self._make_call(ti, td, tdv, session, sv, root=None,
                               detail=TaskCallStatusDetail.WAITING_QUEUE)
        AgentTaskCall.objects.filter(pk=root.pk).update(session_root_task=root)

        parent = self._make_call(ti, td, tdv, session, sv, root=root,
                                 detail=TaskCallStatusDetail.WAITING_QUEUE)
        run = AgentTaskRun.objects.create(
            agent_task_call=parent, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )
        AgentTaskRun.objects.filter(pk=run.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )
        ref = self._make_call(ti, td, tdv, session, sv, root=root,
                              detail=TaskCallStatusDetail.WAITING_DEPENDENCY)
        run.taskrun_result_references.add(ref)

        # A sibling appears ACTIVE_RUNNING but is itself stuck waiting on refs
        # (E5 circular deadlock) — its own run is WAITING_RESULTTASKS.
        sibling = self._make_call(ti, td, tdv, session, sv, root=root,
                                  detail=TaskCallStatusDetail.ACTIVE_RUNNING)
        AgentTaskRun.objects.create(
            agent_task_call=sibling, task_instance=ti, task_definition_version=tdv,
            session_version=sv, arguments_json={},
            requires_approval=False, max_subtask_errors=0,
            max_subtask_error_rate=0, limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1, priority=0,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        )

        _resolve_stuck_waiting_runs()

        run.refresh_from_db()
        assert run.status == TaskRunStatus.FAILURE
