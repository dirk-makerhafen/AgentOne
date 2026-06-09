import pytest
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskCallStatusDetail, TaskRunStatus, TaskType


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
