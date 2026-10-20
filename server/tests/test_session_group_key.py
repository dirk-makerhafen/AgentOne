"""Session ``group_key`` storage and propagation tests."""
from __future__ import annotations

from django.test import TestCase

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.settings import SettingsModel


class GroupKeyTest(TestCase):
    def setUp(self):
        from runtime.session.session import Session as RuntimeSession

        self.agent = AgentModel.objects.create(name="gk-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=SettingsModel.objects.create()
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(latest_agent_version=self.av)
        self.agent.refresh_from_db()

        self.session = SessionModel.objects.create(name="gk-parent")
        self.sv = SessionVersionModel.objects.create(
            session=self.session,
            agent=self.agent,
            pinned_agent_version=self.av,
        )
        SessionModel.objects.filter(pk=self.session.pk).update(
            latest_session_version=self.sv
        )
        self.session.refresh_from_db()
        self.rt = RuntimeSession(
            session_model=self.session, pinned_session_version=self.sv
        )

    def test_get_or_create_session_stores_group_key(self):
        sv = self.av.get_or_create_session(name="gk-top", group_key="wiki:ingest")
        self.assertEqual(sv.session.group_key, "wiki:ingest")

    def test_existing_blank_group_key_is_backfilled(self):
        first = self.av.get_or_create_session(name="gk-singleton")
        self.assertEqual(first.session.group_key, "")

        second = self.av.get_or_create_session(
            name="gk-singleton", group_key="wiki:ingest"
        )
        self.assertEqual(second.session.pk, first.session.pk)
        second.session.refresh_from_db()
        self.assertEqual(second.session.group_key, "wiki:ingest")

    def test_group_key_is_not_part_of_session_identity(self):
        first = self.av.get_or_create_session(
            name="gk-singleton-2", group_key="wiki:ingest"
        )
        second = self.av.get_or_create_session(
            name="gk-singleton-2", group_key="wiki:timeline"
        )
        self.assertEqual(second.session.pk, first.session.pk)
        second.session.refresh_from_db()
        self.assertEqual(second.session.group_key, "wiki:ingest")

    def test_fork_propagates_group_key(self):
        child = self.rt.fork(name="gk-fork", group_key="wiki:timeline-daily")
        self.assertEqual(child.group_key, "wiki:timeline-daily")

    def test_spawn_subagent_propagates_group_key(self):
        child = self.rt.spawn_subagent(
            self.av, name="gk-spawn", group_key="workitem:execute"
        )
        self.assertIsNotNone(child)
        self.assertEqual(child.group_key, "workitem:execute")

    def test_group_key_is_not_inherited_implicitly(self):
        self.session.atomic_update(group_key="wiki:parent-group")
        self.rt.model.refresh_from_db()

        forked = self.rt.fork(name="gk-fork-no-key")
        spawned = self.rt.spawn_subagent(self.av, name="gk-spawn-no-key")

        self.assertEqual(forked.group_key, "")
        self.assertIsNotNone(spawned)
        self.assertEqual(spawned.group_key, "")

    def test_set_group_key_does_not_create_a_session_version(self):
        before = SessionVersionModel.objects.filter(session=self.session).count()

        self.rt.set_group_key("wiki:timeline-review")

        self.session.refresh_from_db()
        self.assertEqual(self.session.group_key, "wiki:timeline-review")
        self.assertEqual(
            SessionVersionModel.objects.filter(session=self.session).count(), before
        )
