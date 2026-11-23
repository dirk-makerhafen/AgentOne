"""Contract tests for the self-contained compaction mixin.

The mixin owns the whole ``compact`` script group and installs an inline
``before:`` hook on ``decide_next_step``. These tests pin the manifest shape
so swapping the mixin stays a one-line ``extends`` change.
"""
import frontmatter
from django.test import SimpleTestCase

from registry.loader.load_agent_manifest import _validate_hooks
from runtime import hooks as hookmod

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIXIN_DIR = (
    _REPO_ROOT / ".agentone" / "agents" / "internal" / "compaction-mixin"
)
_AGENT_MD = _MIXIN_DIR / "agent.md"
_SCRIPTS_MD = _MIXIN_DIR / "scripts" / "scripts.md"
_CORE_SCRIPTS_MD = _REPO_ROOT / ".agentone" / "scripts" / "core" / "scripts.md"


class CompactionMixinHooksTest(SimpleTestCase):
    def _entries(self):
        return _validate_hooks(
            frontmatter.load(str(_AGENT_MD)).get("hooks"), "compaction-mixin"
        )

    def test_hook_is_inline_and_blocks_decide_next_step(self):
        hooks = self._entries()
        self.assertEqual(len(hooks), 1)
        hook = hooks[0]
        self.assertEqual(hook["before"], "compact_if_needed")
        self.assertEqual(hook["mode"], "inline")
        self.assertEqual(hook["on_error"], "fail_closed")
        self.assertEqual(hook["match"]["name"], "decide_next_step")

    def test_intercept_fires_for_turns_but_not_framework_forks(self):
        entries = self._entries()
        base = {
            "def_name": "decide_next_step",
            "def_type": "task",
            "session_name": "s",
            "session_type": "session",
        }
        self.assertEqual(
            [h["name"] for h in hookmod.matching_intercepts(entries, "before", base)],
            ["compact-before-decide"],
        )
        for session_type in ("subtask_hook", "subtask_compact", "test"):
            with self.subTest(session_type=session_type):
                ctx = dict(base, session_type=session_type)
                self.assertEqual(
                    hookmod.matching_intercepts(entries, "before", ctx), []
                )

    def test_hook_tasks_never_trigger_the_hook(self):
        entries = self._entries()
        ctx = {
            "def_name": "compact_if_needed",
            "def_type": "task",
            "session_name": "s",
            "session_type": "session",
        }
        self.assertEqual(hookmod.matching_intercepts(entries, "before", ctx), [])


class CompactionMixinManifestTest(SimpleTestCase):
    def test_mixin_owns_the_whole_compact_group(self):
        data = frontmatter.load(str(_SCRIPTS_MD)).to_dict()
        self.assertEqual(data["group"], "compact")
        tasks = {t["name"] for t in data["tasks"]}
        self.assertEqual(
            tasks,
            {
                "build_llm_compact_context",
                "ingest_compaction",
                "ingest_compaction_response",
                "compact_if_needed",
                "compact_turn",
            },
        )
        commands = {c["name"] for c in data["commands"]}
        self.assertEqual(commands, {"compact"})

    def test_compact_if_needed_is_no_longer_a_process_turn_step(self):
        data = frontmatter.load(str(_CORE_SCRIPTS_MD)).to_dict()
        chains = {c["name"]: c["chain"] for c in data["tasks"] if c.get("type") == "chain"}
        self.assertNotIn("compact_if_needed", chains["process_turn"])
        self.assertIn("decide_next_step", chains["process_turn"])
