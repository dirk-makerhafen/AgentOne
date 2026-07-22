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
