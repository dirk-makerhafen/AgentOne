"""Contract tests for the self-contained memory mixin.

The mixin persists reflection/compaction reports into the memory tree as
detached ``after:`` hooks on ``ingest_reflection_result`` and
``ingest_compaction``. These tests pin the manifest shape so swapping the
mixin stays a one-line ``extends`` change.
"""
import frontmatter
from django.test import SimpleTestCase

from registry.loader.load_agent_manifest import _validate_hooks
from runtime import hooks as hookmod

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIXIN_DIR = (
    _REPO_ROOT / ".agentone" / "agents" / "internal" / "memory-mixin"
)
_AGENT_MD = _MIXIN_DIR / "agent.md"
_SCRIPTS_MD = _MIXIN_DIR / "scripts" / "scripts.md"


class MemoryMixinHooksTest(SimpleTestCase):
    def _entries(self):
        return _validate_hooks(
            frontmatter.load(str(_AGENT_MD)).get("hooks"), "memory-mixin"
        )

    def test_hooks_are_detached_after_ingest(self):
        hooks = self._entries()
        self.assertEqual(len(hooks), 2)
        by_match = {h["match"]["name"]: h for h in hooks}
        self.assertIn("ingest_reflection_result", by_match)
        self.assertIn("ingest_compaction", by_match)
        for h in hooks:
            self.assertEqual(h["after"], "persist_memory_report")
            self.assertEqual(h["mode"], "detached")
            self.assertEqual(h["on_error"], "fail_open")

    def test_intercept_fires_for_ingest_but_not_framework_forks(self):
        entries = self._entries()
        for def_name in ("ingest_reflection_result", "ingest_compaction"):
            base = {
                "def_name": def_name,
                "def_type": "task",
                "session_name": "s",
                "session_type": "session",
            }
            fired = hookmod.matching_intercepts(entries, "after", base)
            self.assertEqual(
                [h["name"] for h in fired],
                [
                    "save-reflection-after-ingest"
                    if def_name == "ingest_reflection_result"
                    else "save-compaction-after-ingest"
                ],
            )
            for session_type in ("subtask_hook", "subtask_compact", "test"):
                with self.subTest(def_name=def_name, session_type=session_type):
                    ctx = dict(base, session_type=session_type)
                    self.assertEqual(hookmod.matching_intercepts(entries, "after", ctx), [])

    def test_hook_tasks_never_trigger_the_hook(self):
        entries = self._entries()
        ctx = {
            "def_name": "persist_memory_report",
            "def_type": "task",
            "session_name": "s",
            "session_type": "session",
        }
        self.assertEqual(hookmod.matching_intercepts(entries, "after", ctx), [])


class MemoryMixinManifestTest(SimpleTestCase):
    def test_mixin_owns_persist_task(self):
        data = frontmatter.load(str(_SCRIPTS_MD)).to_dict()
        self.assertEqual(data["group"], "memory")
        tasks = {t["name"] for t in data["tasks"]}
        self.assertEqual(tasks, {"persist_memory_report"})
        t = data["tasks"][0]
        self.assertTrue(t["bound"])
        self.assertEqual(t["function"], "persist_memory_report")
        self.assertEqual(t["file"], "persist_report.py")
