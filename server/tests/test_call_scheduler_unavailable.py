"""Regression tests for calls whose task cannot be resolved.

When a picked-up call cannot create an :class:`AgentTaskRun` (the session's
agent no longer exposes the task and there is no pinned version to fall back
to), the scheduler used to cancel it silently: the query flipped to
``SUCCESS`` later with no response.  It must now fail the call and surface the
error on the query/response.
"""
from __future__ import annotations

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.task_enums import (
    TaskCallStatus,
    TaskCallStatusDetail,
    TaskExecutionMode,
    TaskType,
)
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance


class UnavailableTaskFailureTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="unavailable-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=SettingsModel.objects.create()
        )
        self.session = SessionModel.objects.create(name="unavailable-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session, agent=self.agent, pinned_agent_version=self.av
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()

        self.td = TaskDefinition.objects.create(name="call_llm")
        self.tdv = TaskDefinitionVersion.objects.create(
            task_definition=self.td,
            description="",
            function_schema={},
            task_type=TaskType.TASK,
            task_execution_mode=TaskExecutionMode.FUNCTION,
            requires_approval=False,
        )
        TaskDefinition.objects.filter(pk=self.td.pk).update(
            latest_task_version=self.tdv
        )
        self.ti = TaskInstance.objects.create(
            session=self.session,
            session_version=self.sv,
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
        self.query = Query.objects.create(
            session=self.session, session_version=self.sv
        )
        self.call = AgentTaskCall.objects.create(
            session=self.session,
            session_version=self.sv,
            task_instance=self.ti,
            task_definition=self.td,
            # No pinned version to fall back to — the run cannot be created.
            task_definition_version=None,
            carguments_json={"*": [{"_type": "Query", "pk": self.query.pk}]},
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=0,
            max_retries=0,
            retry_delay=0,
            retry_requires_approval=False,
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        )

    def test_unavailable_task_fails_call_and_query(self):
        from runtime.tasks.call_scheduler import CallScheduler

        CallScheduler.start_new_taskrun(self.call.pk)

        self.call.refresh_from_db()
        self.assertEqual(self.call.status, TaskCallStatus.ENDED)
        self.assertEqual(
            self.call.status_detail, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
        )

        self.query.refresh_from_db()
        self.assertEqual(self.query.status, QueryStatus.FAILURE)

        response = Response.objects.filter(query=self.query).order_by("-pk").first()
        self.assertIsNotNone(response)
        self.assertEqual(response.status, ResponseStatus.FAILURE)
        self.assertEqual(response.error_type, "task_unavailable")
        self.assertIn("call_llm", response.error_message)
