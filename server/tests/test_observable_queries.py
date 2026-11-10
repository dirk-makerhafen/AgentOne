"""Tests for callback-based observable ORM subscriptions."""
from __future__ import annotations

import threading
from unittest.mock import patch

import fakeredis
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from server.models import observables
from runtime.observable_queries import (
    ObservableProject,
    ObservableRoot,
    ObservableSession,
    ObservableSubscription,
    ObservableWorkspace,
)
from server.models.agents.agent import AgentModel
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.project import Project
from server.models.skills.skill import SkillModel
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from server.models.system import System
from server.tests.dc_test_helpers import create_agent, create_session


class ObservableSubscriptionTest(TestCase):
    def setUp(self):
        self.redis = fakeredis.FakeStrictRedis(decode_responses=True)
        patcher = patch.object(observables, "get_redis", return_value=self.redis)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_root_api_sends_initial_serialized_snapshot(self):
        project = Project.objects.create(name="observable-project")
        events = []

        with CaptureQueriesContext(connection) as captured_queries:
            subscription = ObservableRoot().get_projects(events.append)
        self.addCleanup(subscription.close)

        self.assertFalse(any("ORDER BY" in query["sql"].upper() for query in captured_queries))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "snapshot")
        self.assertEqual(events[0]["items"][0]["pk"], project.pk)
        self.assertEqual(events[0]["items"][0]["name"], project.name)
        self.assertTrue(events[0]["items"][0]["revision"])
        self.assertEqual(subscription.keys, ("Project",))
        self.assertTrue(any(
            "Project" in str(key) for key in self.redis.keys("agentone:obs:*")
        ))

    def test_subscribe_before_initial_read_buffers_events(self):
        events = []
        subscription = ObservableSubscription(
            events.append,
            Project,
            lambda item: item["model"] == "Project",
        )
        self.addCleanup(subscription.close)
        subscription.start(("Project",))
        event_item = {
            "model": "Project",
            "pk": 42,
            "revision": "2026-11-08T00:00:00Z",
            "name": "created-during-read",
        }

        subscription.dispatch({
            "model": "Project",
            "pk": 42,
            "action": "create",
            "data": {"object": event_item},
        })
        self.assertEqual(events, [])

        subscription.initialize([])

        self.assertEqual([event["type"] for event in events], ["snapshot", "upsert"])
        self.assertEqual(events[1]["item"]["pk"], 42)

    def test_unrelated_model_wide_event_does_not_emit_spurious_remove(self):
        events = []
        subscription = ObservableSubscription(
            events.append,
            AgentModel,
            lambda item: (
                item["model"] == "AgentModel"
                and item.get("parent_project_id") == 7
            ),
        )
        subscription.initialize([])
        subscription.dispatch({
            "model": "AgentModel",
            "pk": 42,
            "action": "update",
            "data": {"object": {
                "model": "AgentModel",
                "pk": 42,
                "parent_project_id": 8,
                "revision": "2026-11-08T00:00:00Z",
            }},
        })

        self.assertEqual([event["type"] for event in events], ["snapshot"])

    def test_project_and_session_named_queries_use_scoped_keys(self):
        project = Project.objects.create(name="observable-project-scope")
        agent, version = create_agent("observable-session-agent")
        session, _ = create_session(agent, version)
        message = Message.objects.create(
            role=MessageRole.USER,
            session=session,
            session_version=session.latest_session_version,
        )
        project_events = []
        session_events = []
        project_update_received = threading.Event()

        def capture_project_event(event):
            project_events.append(event)
            if event["type"] == "upsert":
                project_update_received.set()

        project_subscription = ObservableProject(project).get_agents(capture_project_event)
        session_subscription = ObservableSession(session).get_messages(session_events.append)
        self.addCleanup(project_subscription.close)
        self.addCleanup(session_subscription.close)

        project_agent = AgentModel.objects.create(
            name="project-agent",
            parent_project=project,
        )
        self.assertTrue(project_update_received.wait(2))

        self.assertEqual(project_events[0]["type"], "snapshot")
        self.assertEqual(project_events[-1]["item"]["pk"], project_agent.pk)
        self.assertEqual(project_subscription.keys, (
            "AgentModel",
            f"AgentModel.parent_project:{project.pk}",
        ))
        self.assertEqual(session_events[0]["items"][0]["pk"], message.pk)
        self.assertEqual(session_subscription.keys, (
            "Message",
            f"Message.session:{session.pk}",
        ))

    def test_project_list_receives_updates_and_removals_for_child_models(self):
        project = Project.objects.create(name="observable-project-child-updates")
        skill = SkillModel.objects.create(
            name="observable-skill-before",
            parent_project=project,
        )
        skill_pk = skill.pk
        events = []
        update_received = threading.Event()
        remove_received = threading.Event()

        def capture(event):
            events.append(event)
            if event["type"] == "upsert" and event["item"]["pk"] == skill_pk:
                update_received.set()
            elif event["type"] == "remove" and event["pk"] == skill_pk:
                remove_received.set()

        subscription = ObservableProject(project).get_skills(capture)
        self.addCleanup(subscription.close)

        skill.name = "observable-skill-after"
        skill.save()
        self.assertTrue(update_received.wait(2))
        update_event = next(
            event for event in events
            if event["type"] == "upsert" and event["item"]["pk"] == skill_pk
        )
        self.assertEqual(update_event["item"]["name"], "observable-skill-after")

        skill.delete()
        self.assertTrue(
            remove_received.wait(2),
            f"Expected removal; events={events!r}",
        )

    def test_filtered_session_subscription_emits_remove_when_row_stops_matching(self):
        agent, version = create_agent("observable-active-agent")
        session, _ = create_session(agent, version)
        child = SessionModel.objects.create(
            name="inactive-child",
            parent_session=session,
            is_active=False,
        )
        events = []
        subscription = ObservableSession(session).get_active_child_sessions(events.append)
        self.addCleanup(subscription.close)
        self.assertEqual(events[0]["items"], [])
        event_received = threading.Event()
        original_callback = subscription.callback

        def capture(event):
            original_callback(event)
            if event["type"] in ("upsert", "remove"):
                event_received.set()

        subscription.callback = capture
        child.is_active = True
        child.save()

        self.assertTrue(event_received.wait(2))
        self.assertEqual(events[-1]["type"], "upsert")
        self.assertEqual(events[-1]["item"]["pk"], child.pk)
        event_received.clear()
        child.is_active = False
        child.save()
        self.assertTrue(event_received.wait(2))
        self.assertEqual(events[-1]["type"], "remove")

    def test_workspace_scope_and_secret_field_redaction(self):
        workspace = WorkspaceModel.objects.create(
            name="observable-workspace",
            path="/tmp/observable-workspace",
        )
        events = []
        subscription = ObservableWorkspace(workspace).get_terminals(events.append)
        self.addCleanup(subscription.close)

        api_key_data = ApiKey(key="do-not-publish").serialize_observable()
        provider_data = ApiProvider(
            name="observable-provider", default_api_key="do-not-publish"
        ).serialize_observable()
        system_data = System(executor_api_key="do-not-publish").serialize_observable()

        self.assertEqual(subscription.keys, (
            "TerminalSession",
            f"TerminalSession.workspace:{workspace.pk}",
        ))
        self.assertNotIn("key", api_key_data)
        self.assertNotIn("default_api_key", provider_data)
        self.assertNotIn("executor_api_key", system_data)

    def test_root_does_not_expose_generic_query_shapes(self):
        root = ObservableRoot()

        self.assertFalse(hasattr(root, "get_all"))
        self.assertFalse(hasattr(root, "get_related"))
