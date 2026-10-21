"""Tests for the one-time session bootstrap (``runtime/session_bootstrap.py``)."""
from __future__ import annotations

import os
import sys
import tempfile

from django.test import TestCase

from runtime import guidance_files
from runtime.session_bootstrap import (
    COMPACTION_BOOTSTRAP_SENTINEL,
    bootstrap_context,
    ensure_session_bootstrap,
)
from server.models.content import GenericContent
from server.models.enums.message_enums import (
    MessageContentType,
    MessagePartType,
    MessageRole,
)
from server.models.message import Message, MessagePart

COMPACT_SCRIPTS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", ".agentone", "scripts", "compact",
)


def _write(root: str, rel: str, content: str = "x") -> str:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


class SessionBootstrapTest(TestCase):
    def setUp(self):
        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.settings import SettingsModel
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel
        from server.models.workspace import WorkspaceModel

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        _write(self.tmp.name, "AGENTS.md", "root rules")

        settings = SettingsModel.objects.create(
            autoload={
                "files": ["AGENTS.md"],
                "maxFiles": 10,
                "maxChars": 32768,
                "maxCharsPerFile": 8192,
            },
            session_bootstrap=GenericContent.from_text(
                "Workspace: {{workspace_dir}}\n"
                "Session: {{session_dir}}\n"
                "Project: {{project_dir}}"
            ),
        )
        self.agent = AgentModel.objects.create(name="bootstrap-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=settings
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av
        )
        self.workspace = WorkspaceModel.objects.create(
            name="bootstrap-ws", path=self.tmp.name
        )
        self.session_model = SessionModel.objects.create(name="bootstrap-session")
        self.sv = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=self.agent,
            pinned_agent_version=self.av,
            workspace=self.workspace,
            version_number=1,
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            latest_session_version=self.sv
        )
        self.session_model.refresh_from_db()
        from runtime.session.session import Session

        self.runtime = Session(session_model=self.session_model)
        guidance_files.clear_guidance_cache(self.session_model.pk)
        self.addCleanup(
            guidance_files.clear_guidance_cache, self.session_model.pk
        )

    def _user_message(self, text, prev=None):
        msg = Message.objects.create(
            session=self.sv.session,
            session_version=self.sv,
            role=MessageRole.USER,
            prev_message=prev,
        )
        MessagePart.objects.create(
            message=msg,
            type=MessagePartType.MESSAGE,
            content=GenericContent.from_text(text),
            content_type=MessageContentType.TEXT,
        )
        return msg

    def test_first_call_creates_agent_and_guidance_messages(self):
        trigger = self._user_message("hello")
        created = ensure_session_bootstrap(self.runtime, trigger)
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].role, MessageRole.SYSTEM)
        self.assertEqual(created[1].role, MessageRole.USER)
        for message in created:
            self.assertTrue(message.pin_to_context)
        # Chain order: agent bootstrap, guidance, trigger.
        trigger.refresh_from_db()
        self.assertEqual(trigger.prev_message.pk, created[1].pk)
        created[1].refresh_from_db()
        self.assertEqual(created[1].prev_message.pk, created[0].pk)
        bodies = "\n".join(
            str(part.content.get())
            for message in created
            for part in message.parts.order_by("pk")
        )
        self.assertIn("## AGENTS.md\nroot rules", bodies)
        self.assertIn(f"Workspace: {self.tmp.name}", bodies)
        self.assertIn("Session: ", bodies)
        self.assertIn("Project: null", bodies)

    def test_bootstrap_context_contains_session_values(self):
        context = bootstrap_context(self.runtime)
        self.assertEqual(context["workspace_dir"], self.tmp.name)
        self.assertEqual(
            context["workspace_agentone_dir"],
            self.workspace.get_agentone_dir().as_posix(),
        )
        self.assertEqual(context["project_dir"], None)
        self.assertEqual(context["project_agentone_dir"], None)
        self.assertTrue(str(context["session_dir"]).endswith(str(self.session_model.pk)))
        self.assertIsInstance(context["unix_timestamp"], int)
        self.assertEqual(len(context["date"]), 10)
        self.assertEqual(len(context["datetime"]), 19)

    def test_session_bootstrap_chain_is_parent_first(self):
        from server.models.agents.agent import AgentModel
        from server.models.agents.agent_version import AgentVersionModel
        from server.models.settings import SettingsModel

        parent = AgentModel.objects.create(name="bootstrap-parent")
        parent_av = AgentVersionModel.objects.create(
            agent=parent,
            agent_settings=SettingsModel.objects.create(
                session_bootstrap=GenericContent.from_text("parent")
            ),
        )
        child = AgentModel.objects.create(name="bootstrap-child")
        child_av = AgentVersionModel.objects.create(
            agent=child,
            agent_settings=SettingsModel.objects.create(
                session_bootstrap=GenericContent.from_text("child")
            ),
        )
        child_av.extends_agent_versions.set([parent_av])
        self.assertEqual(child_av.collect_session_bootstraps(), ["parent", "child"])

    def test_second_call_is_noop(self):
        trigger = self._user_message("hello")
        ensure_session_bootstrap(self.runtime, trigger)
        count = Message.objects.filter(session=self.sv.session).count()
        again = ensure_session_bootstrap(self.runtime, trigger)
        self.assertEqual(len(again), 2)  # existing bootstraps returned
        self.assertEqual(
            Message.objects.filter(session=self.sv.session).count(), count
        )

    def test_marker_with_bootstrap_suppresses_standalone_messages(self):
        sys.path.insert(0, COMPACT_SCRIPTS)
        try:
            from ingest_compaction import _build_compaction_message
        finally:
            sys.path.remove(COMPACT_SCRIPTS)

        trigger = self._user_message("hello")
        marker = _build_compaction_message(
            self.runtime, newest_compacted=trigger, summary_text="did stuff"
        )
        marker_bodies = "\n".join(
            str(part.content.get())
            for part in marker.parts.order_by("pk")
            if part.content
        )
        self.assertIn(COMPACTION_BOOTSTRAP_SENTINEL, marker_bodies)
        self.assertIn("## AGENTS.md\nroot rules", marker_bodies)
        self.assertIn(f"Workspace: {self.tmp.name}", marker_bodies)

        # A post-compaction turn finds the marker-embedded bootstrap and
        # creates nothing standalone.
        after = self._user_message("next", prev=marker)
        created = ensure_session_bootstrap(self.runtime, after)
        self.assertEqual(created, [])
        self.assertFalse(
            Message.objects.filter(
                session=self.sv.session, pin_to_context=True
            ).exists()
        )
