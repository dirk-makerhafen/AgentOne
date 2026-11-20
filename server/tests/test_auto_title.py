"""Tests for first-message auto-titling of new chats.

The feature mirrors the reflection/compaction forks: a bound task forks the
session, injects a short SYSTEM_NOTICE chain, and a parent-side ingest writes
the fork's ``final_result`` as ``SessionModel.name``.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from server.models.agents.agent import AgentModel
from server.models.enums.message_enums import (
    MessageContentType,
    MessagePartType,
    MessageRole,
    MessageType,
)
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel

_SCRIPTS = Path(__file__).resolve().parents[2] / ".agentone" / "scripts" / "core"


def _load(module_name: str):
    path = _SCRIPTS / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"_auto_title_{module_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutoTitleForkTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = AgentModel.objects.create(name="auto-title-test-agent")
        cls.session = SessionModel.objects.create(name="AgentOne-chat")
        cls.version = SessionVersionModel.objects.create(
            session=cls.session, agent=cls.agent, version_number=1, display_name="AgentOne-chat"
        )
        SessionModel.objects.filter(pk=cls.session.pk).update(latest_session_version=cls.version)

    def _anchor(self, text: str) -> Message:
        msg = Message.objects.create(
            role=MessageRole.USER,
            message_type=MessageType.USER_CHAT,
            session=self.session,
            session_version=self.version,
        )
        msg.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=text,
        )
        return msg

    def test_first_message_text(self):
        mod = _load("auto_title_session")
        self.assertEqual(mod.first_message_text(self._anchor("Fix the login bug")), "Fix the login bug")

    def test_candidate_guard(self):
        mod = _load("auto_title_session")
        specs = [{"role": "user", "message_type": None, "parts": []}]
        self.assertTrue(mod.is_auto_title_candidate(MagicMock(model=self.session), specs))

        # Once a real user chat exists, the session is no longer a candidate.
        self._anchor("Fix the login bug")
        self.assertFalse(mod.is_auto_title_candidate(MagicMock(model=self.session), specs))

    def test_candidate_guard_skips_child_sessions_and_explicit_names(self):
        mod = _load("auto_title_session")
        specs = [{"role": "user", "message_type": None, "parts": []}]
        child = SessionModel.objects.create(
            name="child", parent_session=self.session, session_type=SessionType.SUBTASK_HOOK
        )
        self.assertFalse(mod.is_auto_title_candidate(MagicMock(model=child), specs))
        self.session.name_is_auto = False
        self.assertFalse(mod.is_auto_title_candidate(MagicMock(model=self.session), specs))

    @override_settings(AGENTONE_AUTO_TITLE_ENABLED=False)
    def test_candidate_guard_honours_kill_switch(self):
        mod = _load("auto_title_session")
        self.assertFalse(
            mod.is_auto_title_candidate(
                MagicMock(model=self.session), [{"role": "user", "message_type": None, "parts": []}]
            )
        )

    def test_short_greeting_is_skipped(self):
        mod = _load("auto_title_session")
        parent = MagicMock()
        self.assertIsNone(
            mod.auto_title_session(parent, anchor_message=self._anchor("hi"), expected_name="AgentOne-chat")
        )
        parent.fork.assert_not_called()

    def test_fork_preserves_model_and_cacheable_tool_set(self):
        mod = _load("auto_title_session")
        anchor = self._anchor("Refactor the billing webhook retry logic")
        child = MagicMock()
        child.model.pk = 99
        child.add_user_message.return_value = "child-call"
        parent = MagicMock()
        parent.model.pk = self.session.pk
        parent.name = "AgentOne-chat"
        parent.fork.return_value = child
        ingest = MagicMock()
        parent.get_task.return_value = ingest

        mod.auto_title_session(parent, anchor_message=anchor, expected_name="AgentOne-chat")

        kwargs = parent.fork.call_args.kwargs
        self.assertEqual(kwargs["session_type"], SessionType.SUBTASK_HOOK)
        self.assertEqual(kwargs["group_key"], "internal:auto-title")
        self.assertEqual(kwargs["anchor"], anchor)
        self.assertEqual(kwargs["auto_compact_max_tokens"], 0)
        self.assertEqual(kwargs["auto_compact_idle_seconds"], 0)
        self.assertEqual(kwargs["tool_call_allowlist"], ["final_result"])
        self.assertEqual(kwargs["max_turns"], 2)
        # No model override: the fork inherits the parent's aimodel and tools.
        self.assertNotIn("aimodel", kwargs)
        self.assertEqual(ingest.delay.call_args.kwargs["expected_name"], "AgentOne-chat")
        self.assertEqual(ingest.delay.call_args.kwargs["child_session_pk"], 99)

    @override_settings(AGENTONE_AUTO_TITLE_ENABLED=False)
    def test_force_bypasses_kill_switch(self):
        mod = _load("auto_title_session")
        anchor = self._anchor("Refactor the billing webhook retry logic")
        child = MagicMock()
        child.model.pk = 99
        child.add_user_message.return_value = "child-call"
        parent = MagicMock()
        parent.model.pk = self.session.pk
        parent.name = "AgentOne-chat"
        parent.fork.return_value = child
        ingest = MagicMock()
        parent.get_task.return_value = ingest

        result = mod.auto_title_session(parent, anchor_message=anchor, force=True)

        self.assertEqual(result, ingest.delay.return_value)
        self.assertTrue(ingest.delay.call_args.kwargs["force"])
        parent.fork.assert_called_once()

    def test_manual_command_uses_first_substantive_message(self):
        mod = _load("auto_title_session")
        self._anchor("hi")
        anchor = self._anchor("Refactor the billing webhook retry logic")
        self._anchor("And update its tests")

        with patch.object(mod, "auto_title_session", return_value="call") as title:
            result = mod.auto_title_command(MagicMock(model=self.session))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(title.call_args.kwargs["anchor_message"].pk, anchor.pk)
        self.assertTrue(title.call_args.kwargs["force"])

    def test_manual_command_without_user_message(self):
        mod = _load("auto_title_session")
        result = mod.auto_title_command(MagicMock(model=self.session))
        self.assertEqual(result["status"], "error")

    def test_sanitize_title(self):
        mod = _load("ingest_auto_title")
        self.assertEqual(mod.sanitize_title('  Title: "Fix login bug."  \nmore'), "Fix login bug")
        self.assertEqual(mod.sanitize_title("**Add auth tests**"), "Add auth tests")
        self.assertEqual(mod.sanitize_title(""), "")


class IngestAutoTitleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = AgentModel.objects.create(name="auto-title-ingest-agent")
        cls.session = SessionModel.objects.create(name="AgentOne-chat")
        cls.version = SessionVersionModel.objects.create(
            session=cls.session, agent=cls.agent, version_number=1, display_name="AgentOne-chat"
        )
        SessionModel.objects.filter(pk=cls.session.pk).update(latest_session_version=cls.version)

    def _runtime(self):
        return MagicMock(model=self.session)

    def test_writes_name_and_closes_fork(self):
        mod = _load("ingest_auto_title")
        child = SessionModel.objects.create(
            name="p1:auto-title:child", parent_session=self.session, session_type=SessionType.SUBTASK_HOOK
        )
        with patch.object(mod, "Session") as session_cls:
            out = mod.ingest_auto_title(
                self._runtime(),
                title_result="Fix login bug",
                expected_name="AgentOne-chat",
                child_session_pk=child.pk,
            )
        self.assertIsNotNone(out)
        self.session.refresh_from_db()
        self.version.refresh_from_db()
        self.assertEqual(self.session.name, "Fix login bug")
        self.assertEqual(self.version.display_name, "Fix login bug")
        session_cls.return_value.request_end.assert_called_once_with(reason="auto_title_done")

    def test_manual_rename_during_generation_wins(self):
        mod = _load("ingest_auto_title")
        SessionModel.objects.filter(pk=self.session.pk).update(name="Chosen by user", name_is_auto=False)
        result = mod.ingest_auto_title(
            self._runtime(), title_result="Fix login bug", expected_name="AgentOne-chat"
        )
        self.assertIsNone(result)
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, "Chosen by user")
        self.assertFalse(self.session.name_is_auto)

    def test_force_replaces_manual_name(self):
        mod = _load("ingest_auto_title")
        SessionModel.objects.filter(pk=self.session.pk).update(
            name="Chosen by user", name_is_auto=False
        )
        out = mod.ingest_auto_title(
            self._runtime(),
            title_result="Fix login bug",
            expected_name="AgentOne-chat",
            force=True,
        )
        self.assertIsNotNone(out)
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, "Fix login bug")
        self.assertTrue(self.session.name_is_auto)

    def test_empty_result_is_noop(self):
        mod = _load("ingest_auto_title")
        self.assertIsNone(mod.ingest_auto_title(self._runtime(), title_result=""))
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, "AgentOne-chat")

    def test_collision_gets_suffix(self):
        mod = _load("ingest_auto_title")
        SessionModel.objects.create(name="Fix login bug")
        mod.ingest_auto_title(
            self._runtime(), title_result="Fix login bug", expected_name="AgentOne-chat"
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.name, "Fix login bug 2")
