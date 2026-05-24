"""Tests for the named pipe component: models, merge logic, dispatch helpers."""
from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from server.models.pipe import NamedPipe, NamedPipeSubscription
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel


class NamedPipeModelTest(TestCase):
    """Test NamedPipe model fields and constraints."""

    def test_create_pipe(self):
        pipe = NamedPipe.objects.create(
            name="email.received",
            description="New emails from IMAP",
        )
        self.assertEqual(pipe.name, "email.received")
        self.assertEqual(pipe.description, "New emails from IMAP")
        self.assertIsNotNone(pipe.created_at)

    def test_unique_pipe_name(self):
        NamedPipe.objects.create(name="email.received")
        with self.assertRaises(IntegrityError):
            NamedPipe.objects.create(name="email.received")

    def test_str_method(self):
        pipe = NamedPipe.objects.create(name="scan.ready")
        self.assertEqual(str(pipe), "scan.ready")


class NamedPipeSubscriptionTest(TestCase):
    """Test NamedPipeSubscription model fields and constraints."""

    def setUp(self):
        self.pipe = NamedPipe.objects.create(name="test.pipe")
        td = TaskDefinition.objects.create(name="consumer-task")
        self.consumer = TaskDefinitionVersion.objects.create(
            task_definition=td,
            description="test consumer",
            function_schema={"type": "object", "properties": {}},
            task_type="TASK",
        )

    def test_create_subscription(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
            name="process emails",
        )
        self.assertEqual(sub.pipe.name, "test.pipe")
        self.assertEqual(sub.consumer_task, self.consumer)
        self.assertEqual(sub.name, "process emails")
        self.assertTrue(sub.is_active)
        self.assertEqual(sub.arguments_template, {})

    def test_unique_together_pipe_and_consumer(self):
        NamedPipeSubscription.objects.create(
            pipe=self.pipe, consumer_task=self.consumer,
        )
        with self.assertRaises(IntegrityError):
            NamedPipeSubscription.objects.create(
                pipe=self.pipe, consumer_task=self.consumer,
            )

    def test_inactive_subscription(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
            is_active=False,
        )
        self.assertFalse(sub.is_active)

    def test_str_method_with_name(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
            name="my-sub",
        )
        self.assertIn("my-sub", str(sub))

    def test_str_method_falls_back_to_pipe_name(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
        )
        self.assertIn("test.pipe", str(sub))

    def test_default_session_mode_is_new(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
        )
        self.assertEqual(sub.session_mode, "new")

    def test_existing_session_mode(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
            session_mode="existing",
            session_name="my-persistent-session",
        )
        self.assertEqual(sub.session_mode, "existing")
        self.assertEqual(sub.session_name, "my-persistent-session")

    def test_subscription_with_agent(self):
        agent = AgentModel.objects.create(name="pipe-sub-agent")
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
            agent=agent,
        )
        self.assertEqual(sub.agent, agent)

    def test_subscription_without_agent_defaults_null(self):
        sub = NamedPipeSubscription.objects.create(
            pipe=self.pipe,
            consumer_task=self.consumer,
        )
        self.assertIsNone(sub.agent)


class TaskDefinitionVersionPipeNamesTest(TestCase):
    """Test pipe_output_names on TaskDefinitionVersion."""

    def setUp(self):
        td = TaskDefinition.objects.create(name="producer-task")
        self.tdv = TaskDefinitionVersion.objects.create(
            task_definition=td,
            description="produces to pipes",
            function_schema={"type": "object", "properties": {}},
            task_type="TASK",
            pipe_output_names=["email.received", "item.parsed"],
        )

    def test_pipe_names_stored(self):
        self.assertEqual(
            self.tdv.pipe_output_names,
            ["email.received", "item.parsed"],
        )

    def test_pipe_names_default_to_empty_list(self):
        td2 = TaskDefinition.objects.create(name="plain-task")
        tdv2 = TaskDefinitionVersion.objects.create(
            task_definition=td2,
            description="no pipes",
            function_schema={"type": "object", "properties": {}},
            task_type="TASK",
        )
        self.assertEqual(tdv2.pipe_output_names, [])


class AgentTaskCallPipeNamesTest(TestCase):
    """Test pipe_output_names merge logic in AgentTaskCall.create()."""

    def setUp(self):
        td = TaskDefinition.objects.create(name="producer")
        self.tdv = TaskDefinitionVersion.objects.create(
            task_definition=td,
            description="producer",
            function_schema={"type": "object", "properties": {}},
            task_type="TASK",
            pipe_output_names=["pipe.from.tdv"],
        )
        self.agent = AgentModel.objects.create(name="pipe-test-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent,
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av,
        )
        self.agent.refresh_from_db()
        self.session = SessionModel.objects.create(name="pipe-test-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
            version_number=1,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv,
        )
        self.session.refresh_from_db()
        self.ti = TaskInstance.objects.create(
            task_definition_version=self.tdv,
            session=self.session,
            session_version=self.sv,
            iarguments_json={},
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1,
            max_retries=0,
            retry_delay=10,
            retry_requires_approval=True,
        )

    def test_inherits_tdv_pipe_names(self):
        call = AgentTaskCall.create(
            task_instance=self.ti,
            kwargs={"msg": "hello"},
        )
        self.assertIn("pipe.from.tdv", call.pipe_output_names)

    def test_merges_call_level_pipe_names(self):
        call = AgentTaskCall.create(
            task_instance=self.ti,
            kwargs={"msg": "hello"},
            pipe_output_names=["pipe.from.call"],
        )
        self.assertIn("pipe.from.tdv", call.pipe_output_names)
        self.assertIn("pipe.from.call", call.pipe_output_names)

    def test_deduplicates_pipe_names(self):
        call = AgentTaskCall.create(
            task_instance=self.ti,
            kwargs={"msg": "hello"},
            pipe_output_names=["pipe.from.tdv", "pipe.from.tdv"],
        )
        self.assertEqual(
            call.pipe_output_names.count("pipe.from.tdv"), 1,
        )

    def test_pipe_output_names_serialized(self):
        call = AgentTaskCall.create(
            task_instance=self.ti,
            kwargs={"msg": "hello"},
        )
        call.refresh_from_db()
        self.assertIsInstance(call.pipe_output_names, list)

    def test_no_tdv_pipes_still_allows_call_level(self):
        td2 = TaskDefinition.objects.create(name="plain-producer")
        tdv2 = TaskDefinitionVersion.objects.create(
            task_definition=td2,
            description="plain",
            function_schema={"type": "object", "properties": {}},
            task_type="TASK",
        )
        ti2 = TaskInstance.objects.create(
            task_definition_version=tdv2,
            session=self.session,
            session_version=self.sv,
            iarguments_json={},
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1,
            max_retries=0,
            retry_delay=10,
            retry_requires_approval=True,
        )
        call = AgentTaskCall.create(
            task_instance=ti2,
            kwargs={"x": 1},
            pipe_output_names=["pipe.manual"],
        )
        self.assertEqual(call.pipe_output_names, ["pipe.manual"])
