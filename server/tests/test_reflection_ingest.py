"""Tests for the reflection mixin's parent-side ingest.

``ingest_reflection_result`` inserts the fork's report into the observed
session as a ``role=INFO`` / ``message_type=REFLECTION`` message placed after
the session-end anchor (see ``.agentone/agents/internal/reflection-mixin/``).
"""
import importlib.util
from pathlib import Path

import frontmatter
from django.test import TestCase

from registry.loader.load_agent_manifest import _validate_hooks
from runtime import hooks as hookmod
from server.models.enums.message_enums import MessageRole, MessageType
from server.models.message import Message
from server.tests.helpers import AgentMdTestMixin

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIXIN_DIR = (
    _REPO_ROOT / ".agentone" / "agents" / "internal" / "reflection-mixin"
)
_MIXIN_AGENT_MD = _MIXIN_DIR / "agent.md"


def _load_reflection_module():
    """Load the reflection-mixin ``reflect_session.py`` as a module."""
    path = _MIXIN_DIR / "scripts" / "reflect_session.py"
    spec = importlib.util.spec_from_file_location("_reflection_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReflectIngestTest(AgentMdTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_extract_report_text(self):
        mod = _load_reflection_module()
        self.assertEqual(mod._extract_report_text("hello"), "hello")
        self.assertEqual(mod._extract_report_text(None), "")
        self.assertEqual(mod._extract_report_text({"content": "x"}), "x")

    def test_ingest_inserts_reflection_after_anchor(self):
        mod = _load_reflection_module()
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        anchor = runtime._persist_message(content="anchor")
        out = mod.ingest_reflection_result(
            runtime, anchor_message=anchor, reflection_result="the report"
        )
        self.assertIsNotNone(out)
        new = Message.objects.get(pk=out.pk)
        self.assertEqual(new.role, MessageRole.INFO)
        self.assertEqual(new.message_type, MessageType.REFLECTION)
        self.assertEqual(new.prev_message_id, anchor.pk)
        self.assertIn("the report", new.parts.first().content.get())

    def test_ingest_midchain_relinks_successor(self):
        mod = _load_reflection_module()
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        anchor = runtime._persist_message(content="anchor")
        # A message arrived after the session ended but before the reflection
        # returned (e.g. the user resumed).
        follower = runtime._persist_message(content="follower")
        out = mod.ingest_reflection_result(
            runtime, anchor_message=anchor, reflection_result="the report"
        )
        follower.refresh_from_db()
        self.assertEqual(out.prev_message_id, anchor.pk)
        self.assertEqual(follower.prev_message_id, out.pk)
        # Single linear chain: anchor has exactly one successor (the report).
        self.assertEqual(anchor.next_messages.count(), 1)

    def test_ingest_empty_report_is_noop(self):
        mod = _load_reflection_module()
        session = self.create_session(self.agent, self.av)
        runtime = session.get_runtime()
        anchor = runtime._persist_message(content="anchor")
        self.assertIsNone(
            mod.ingest_reflection_result(
                runtime, anchor_message=anchor, reflection_result=""
            )
        )
        self.assertEqual(anchor.next_messages.count(), 0)


class ReflectionMixinHooksTest(TestCase):
    """The mixin declares a detached before-hook on ``compact_turn``."""

    def _entries(self):
        return _validate_hooks(
            frontmatter.load(str(_MIXIN_AGENT_MD)).get("hooks"), "reflection-mixin"
        )

    def test_before_compact_hook_shape(self):
        by_name = {h["name"]: h for h in self._entries()}
        hook = by_name["reflect-before-compact"]
        self.assertEqual(hook["before"], "reflect_session")
        self.assertEqual(hook["mode"], "detached")
        self.assertEqual(hook["match"]["name"], "compact_turn")

    def test_before_intercept_fires_for_compact_turn_only(self):
        entries = self._entries()
        base = {
            "def_name": "compact_turn",
            "def_type": "task",
            "session_name": "s",
            "session_type": "session",
        }
        fired = hookmod.matching_intercepts(entries, "before", base)
        self.assertEqual([h["name"] for h in fired], ["reflect-before-compact"])
        # Framework worker forks never fire intercepts (recursion guard).
        fork = dict(base, session_type="subtask_hook")
        self.assertEqual(hookmod.matching_intercepts(entries, "before", fork), [])
