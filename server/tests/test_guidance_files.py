"""Tests for guidance-file autoload + index/hint (spec ``docs/agents-md.md`` §4)."""
from __future__ import annotations

import os
import sys
import tempfile

from django.test import SimpleTestCase, TestCase

from runtime import guidance_files
from runtime.guidance_files import (
    GuidanceSection,
    build_index,
    chain_for_directory,
    get_autoload_config,
    get_guidance_file_index_enabled,
    get_guidance_file_index_limit,
    hint_for_call,
    hint_line,
    load_sections,
    render_autoload_message,
    render_index_message,
    resolve_patterns,
    validate_autoload_block,
)
from runtime.workspace_access import ActionPolicy, WorkspaceAccessPolicy
from server.tests.helpers import AgentMdTestMixin

CORE_SCRIPTS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", ".agentone", "scripts", "core",
)


def _allow_all(root) -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(workspace_root=root)


def _write(root: str, rel: str, content: str = "x") -> str:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


class ValidateAutoloadBlockTest(SimpleTestCase):
    def test_defaults_when_empty_mapping(self):
        cfg = validate_autoload_block({})
        self.assertEqual(cfg, {"files": []})

    def test_string_files_becomes_list(self):
        cfg = validate_autoload_block({"files": "AGENTS.md"})
        self.assertEqual(cfg["files"], ["AGENTS.md"])

    def test_full_block_round_trips(self):
        cfg = validate_autoload_block({
            "files": ["AGENTS.md", "**/extra.md"],
            "maxFiles": 5,
            "maxChars": 10000,
            "maxCharsPerFile": 4000,
        })
        self.assertEqual(cfg["files"], ["AGENTS.md", "**/extra.md"])
        self.assertEqual(cfg["maxFiles"], 5)
        self.assertNotIn("index", cfg)

    def test_legacy_index_subkey_rejected_with_pointer(self):
        with self.assertRaises(ValueError) as ctx:
            validate_autoload_block({"files": ["AGENTS.md"], "index": True})
        self.assertIn("loadGuidanceFileIndex", str(ctx.exception))

    def test_rejects_non_mapping(self):
        with self.assertRaises(ValueError):
            validate_autoload_block(["AGENTS.md"])

    def test_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            validate_autoload_block({"files": ["AGENTS.md"], "bogus": 1})

    def test_rejects_escape_patterns(self):
        for bad in ("/abs.md", "~/home.md", "../escape.md", "a/../../b.md"):
            with self.assertRaises(ValueError, msg=bad):
                validate_autoload_block({"files": [bad]})

    def test_rejects_bad_budgets(self):
        for key in ("maxFiles", "maxChars", "maxCharsPerFile"):
            with self.assertRaises(ValueError, msg=key):
                validate_autoload_block({key: -1})
            with self.assertRaises(ValueError, msg=key):
                validate_autoload_block({key: True})
            with self.assertRaises(ValueError, msg=key):
                validate_autoload_block({key: "10"})


class ResolvePatternsTest(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        from pathlib import Path

        self.root_path = Path(self.root).resolve()
        _write(self.root, "AGENTS.md", "root")
        _write(self.root, "docs/AGENTS.md", "docs")
        _write(self.root, "docs/deep/AGENTS.md", "deep")
        _write(self.root, "docs/notes.md", "notes")
        _write(self.root, "other/extra.md", "extra")

    def tearDown(self):
        self.tmp.cleanup()

    def _rel(self, paths):
        from pathlib import Path

        return sorted(p.resolve().relative_to(self.root_path.resolve()).as_posix() for p in paths)

    def test_bare_name_matches_root_only(self):
        paths, omitted = resolve_patterns(
            self.root_path, ["AGENTS.md"], _allow_all(self.root_path), 10
        )
        self.assertEqual(self._rel(paths), ["AGENTS.md"])
        self.assertEqual(omitted, 0)

    def test_star_star_recurses(self):
        paths, omitted = resolve_patterns(
            self.root_path, ["**/AGENTS.md"], _allow_all(self.root_path), 10
        )
        self.assertEqual(
            self._rel(paths),
            ["AGENTS.md", "docs/AGENTS.md", "docs/deep/AGENTS.md"],
        )
        self.assertEqual(omitted, 0)

    def test_single_star_does_not_cross_slash(self):
        paths, _ = resolve_patterns(
            self.root_path, ["docs/*.md"], _allow_all(self.root_path), 10
        )
        self.assertEqual(self._rel(paths), ["docs/AGENTS.md", "docs/notes.md"])

    def test_config_order_and_dedup(self):
        paths, _ = resolve_patterns(
            self.root_path,
            ["**/AGENTS.md", "AGENTS.md"],
            _allow_all(self.root_path),
            10,
        )
        # First pattern already covers the root file — no duplicate.
        self.assertEqual(len(paths), 3)

    def test_max_files_cut_reports_omitted(self):
        paths, omitted = resolve_patterns(
            self.root_path, ["**/AGENTS.md"], _allow_all(self.root_path), 2
        )
        self.assertEqual(len(paths), 2)
        self.assertEqual(omitted, 1)
        # Deterministic: shallow-first wins the cap.
        self.assertEqual(self._rel(paths), ["AGENTS.md", "docs/AGENTS.md"])

    def test_directories_never_match(self):
        os.makedirs(os.path.join(self.root, "AGENTS.md.d"), exist_ok=True)
        paths, _ = resolve_patterns(
            self.root_path, ["AGENTS.md*"], _allow_all(self.root_path), 10
        )
        self.assertEqual(self._rel(paths), ["AGENTS.md"])

    def test_deny_policy_skips_silently(self):
        policy = WorkspaceAccessPolicy(
            workspace_root=self.root_path,
            inside_read=ActionPolicy(default="allow", deny=["docs/**"]),
        )
        paths, _ = resolve_patterns(
            self.root_path, ["**/AGENTS.md"], policy, 10
        )
        self.assertEqual(self._rel(paths), ["AGENTS.md"])

    def test_symlink_escape_skipped(self):
        import pathlib

        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = os.path.join(outside.name, "secret.md")
        _write(outside.name, "secret.md", "secret")
        os.symlink(secret, os.path.join(self.root, "linked.md"))
        ok_target = os.path.join(self.root, "docs", "notes.md")
        os.symlink(ok_target, os.path.join(self.root, "inner-link.md"))
        paths, _ = resolve_patterns(
            self.root_path, ["*.md"], _allow_all(self.root_path), 10
        )
        rels = self._rel(paths)
        self.assertIn("AGENTS.md", rels)
        # inner-link.md resolves to docs/notes.md (same file, no duplicate).
        self.assertIn("docs/notes.md", rels)
        self.assertNotIn("linked.md", rels)


class LoadSectionsTest(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from pathlib import Path

        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _path(self, rel, content):
        full = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
        from pathlib import Path

        return Path(full)

    def test_per_file_cap_marks_truncation(self):
        path = self._path("AGENTS.md", "a" * 100)
        sections = load_sections(self.root, [path], 1000, 10)
        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0].truncated)
        self.assertIn("[truncated: showing first 10 of 100 chars]", sections[0].content)

    def test_total_budget_cuts_overflow_file(self):
        first = self._path("a.md", "a" * 20)
        second = self._path("b.md", "b" * 20)
        sections = load_sections(self.root, [first, second], 25, 1000)
        self.assertEqual(len(sections), 2)
        self.assertFalse(sections[0].truncated)
        self.assertTrue(sections[1].truncated)
        self.assertIn("fit the session autoload budget", sections[1].content)

    def test_zero_budget_disables_contents(self):
        path = self._path("AGENTS.md", "hello")
        self.assertEqual(load_sections(self.root, [path], 0, 100), [])

    def test_unreadable_file_skipped(self):
        from pathlib import Path

        missing = Path(os.path.join(self.tmp.name, "gone.md"))
        self.assertEqual(load_sections(self.root, [missing], 1000, 100), [])


class BuildIndexTest(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        from pathlib import Path

        self.root_path = Path(self.root).resolve()
        _write(self.root, "AGENTS.md", "root")
        _write(self.root, "sub/AGENTS.md", "sub")
        _write(self.root, "sub/deep/AGENTS.md", "deep")
        _write(self.root, "legacy/CLAUDE.md", "claude")

    def tearDown(self):
        self.tmp.cleanup()

    def test_excludes_autoloaded_and_sorts_shallow_first(self):
        rels, omitted = build_index(
            self.root_path, _allow_all(self.root_path), {"AGENTS.md"}, 10
        )
        self.assertEqual(rels, ["legacy/CLAUDE.md", "sub/AGENTS.md", "sub/deep/AGENTS.md"])
        self.assertEqual(omitted, 0)

    def test_limit_with_remainder(self):
        rels, omitted = build_index(
            self.root_path, _allow_all(self.root_path), {"AGENTS.md"}, 2
        )
        self.assertEqual(len(rels), 2)
        self.assertEqual(omitted, 1)

    def test_zero_limit_omits_message_inputs(self):
        rels, omitted = build_index(
            self.root_path, _allow_all(self.root_path), set(), 0
        )
        self.assertEqual(rels, [])
        self.assertEqual(omitted, 4)

    def test_deny_never_advertised(self):
        policy = WorkspaceAccessPolicy(
            workspace_root=self.root_path,
            inside_read=ActionPolicy(default="allow", deny=["sub/**"]),
        )
        rels, _ = build_index(self.root_path, policy, set(), 10)
        self.assertEqual(rels, ["AGENTS.md", "legacy/CLAUDE.md"])


class ChainForDirectoryTest(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from pathlib import Path

        self.root = Path(self.tmp.name)
        _write(self.tmp.name, "AGENTS.md", "root")
        _write(self.tmp.name, "a/AGENTS.md", "a")
        _write(self.tmp.name, "a/b/AGENTS.md", "b")

    def tearDown(self):
        self.tmp.cleanup()

    def test_chain_is_shallow_first(self):
        from pathlib import Path

        target = Path(self.tmp.name) / "a" / "b"
        chain = chain_for_directory(self.root, target)
        rels = [p.relative_to(self.root.resolve()).as_posix() for p in chain]
        self.assertEqual(rels, ["AGENTS.md", "a/AGENTS.md", "a/b/AGENTS.md"])

    def test_outside_root_is_empty(self):
        from pathlib import Path

        self.assertEqual(chain_for_directory(self.root, Path("/etc")), [])


class RenderTest(SimpleTestCase):
    def test_autoload_message_combines_sections(self):
        text = render_autoload_message([
            GuidanceSection(relpath="AGENTS.md", content="root rules"),
            GuidanceSection(relpath="sub/AGENTS.md", content="sub rules"),
        ])
        self.assertIn("advisory guidance", text)
        self.assertIn("## AGENTS.md\nroot rules", text)
        self.assertIn("## sub/AGENTS.md\nsub rules", text)
        self.assertIsNone(render_autoload_message([]))

    def test_index_message_overflow_line(self):
        text = render_index_message(["a/AGENTS.md"], 3)
        self.assertIn("- a/AGENTS.md", text)
        self.assertIn("(+3 more", text)
        self.assertIsNone(render_index_message([], 0))

    def test_hint_line_names_file(self):
        self.assertIn("sub/AGENTS.md", hint_line("sub/AGENTS.md"))


class GuidanceFileLoaderTest(AgentMdTestMixin, TestCase):
    """Loader round-trip for ``autoload:`` + ``agentsMdIndexLimit``."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_autoload_block_round_trips(self):
        agent, av = self.load_agent("autoload_ok")
        settings = av.agent_settings
        self.assertEqual(
            settings.autoload["files"], ["AGENTS.md", "**/extra.md"]
        )
        self.assertEqual(settings.autoload["maxFiles"], 5)
        self.assertEqual(settings.autoload["maxChars"], 10000)
        self.assertEqual(settings.autoload["maxCharsPerFile"], 4000)
        self.assertNotIn("index", settings.autoload)
        self.assertFalse(settings.load_guidance_file_index)
        self.assertEqual(settings.guidance_file_index_limit, 3)
        # Runtime resolution inherits through the version chain.
        self.assertEqual(av.get_runtime().autoload["maxFiles"], 5)
        self.assertFalse(av.get_runtime().load_guidance_file_index)

    def test_escape_pattern_fails_load(self):
        from registry.loader.load_agent_manifest import load_agent_manifest
        from server.tests.helpers import TESTPROJECT

        path = TESTPROJECT / "agents" / "autoload_bad" / "agent.md"
        with self.assertRaises(ValueError):
            load_agent_manifest(path, install_repo=self._install_repo)

    def test_unset_autoload_is_none(self):
        agent, av = self.load_agent("base")
        self.assertIsNone(av.agent_settings.autoload)
        self.assertIsNone(av.get_runtime().autoload)


class GuidanceFileSessionTest(TestCase):
    """Pin/repin, hints, and context wiring against a real workspace."""

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
        _write(self.tmp.name, "sub/AGENTS.md", "sub rules")
        _write(self.tmp.name, "sub/deep/AGENTS.md", "deep rules")

        settings = SettingsModel.objects.create(
            autoload={
                "files": ["AGENTS.md"],
                "maxFiles": 10,
                "maxChars": 32768,
                "maxCharsPerFile": 8192,
            },
            load_guidance_file_index=True,
            guidance_file_index_limit=10,
        )
        self.agent = AgentModel.objects.create(name="guidance-agent")
        self.av = AgentVersionModel.objects.create(
            agent=self.agent, agent_settings=settings
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.av
        )
        self.workspace = WorkspaceModel.objects.create(
            name="guidance-ws", path=self.tmp.name
        )
        self.session_model = SessionModel.objects.create(name="guidance-session")
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

    def test_config_defaults_are_opt_in(self):
        from server.models.settings import SettingsModel

        SettingsModel.objects.filter(
            pk=self.av.agent_settings.pk
        ).update(
            autoload=None,
            load_guidance_file_index=None,
            guidance_file_index_limit=None,
        )
        self.av.refresh_from_db()
        cfg = get_autoload_config(self.runtime)
        self.assertEqual(cfg["files"], [])
        self.assertFalse(get_guidance_file_index_enabled(self.runtime))
        self.assertEqual(get_guidance_file_index_limit(self.runtime), 10)
        autoload_text, index_text = guidance_files.ensure_pinned(self.runtime)
        self.assertIsNone(autoload_text)
        self.assertIsNone(index_text)

    def test_index_disabled_independently_of_autoload(self):
        from server.models.settings import SettingsModel

        SettingsModel.objects.filter(
            pk=self.av.agent_settings.pk
        ).update(load_guidance_file_index=False)
        self.av.refresh_from_db()
        self.assertFalse(get_guidance_file_index_enabled(self.runtime))
        autoload_text, index_text = guidance_files.ensure_pinned(self.runtime)
        self.assertIsNotNone(autoload_text)
        self.assertIsNone(index_text)

    def test_index_without_autoload_content_lists_everything(self):
        from server.models.settings import SettingsModel

        autoload = dict(self.av.agent_settings.autoload)
        autoload["maxChars"] = 0
        SettingsModel.objects.filter(
            pk=self.av.agent_settings.pk
        ).update(autoload=autoload)
        self.av.refresh_from_db()
        autoload_text, index_text = guidance_files.ensure_pinned(self.runtime)
        self.assertIsNone(autoload_text)
        self.assertIn("- AGENTS.md", index_text)
        self.assertIn("- sub/AGENTS.md", index_text)
        self.assertNotIn("already included in full above", index_text)

    def test_ensure_pinned_returns_both_messages(self):
        autoload_text, index_text = guidance_files.ensure_pinned(self.runtime)
        self.assertIn("## AGENTS.md\nroot rules", autoload_text)
        self.assertIn("- sub/AGENTS.md", index_text)
        self.assertIn("- sub/deep/AGENTS.md", index_text)
        self.assertNotIn("AGENTS.md\nroot rules", index_text.replace("## ", ""))

    def test_pin_is_stable_across_turns(self):
        first = guidance_files.ensure_pinned(self.runtime)
        with open(os.path.join(self.tmp.name, "AGENTS.md"), "w") as handle:
            handle.write("edited rules")
        second = guidance_files.ensure_pinned(self.runtime)
        self.assertEqual(first, second)

    def test_hint_once_then_silent(self):
        guidance_files.ensure_pinned(self.runtime)
        target = os.path.join(self.tmp.name, "sub", "notes.txt")
        hint = hint_for_call(
            self.runtime, "read", "read", {"path": target}
        )
        self.assertIsNotNone(hint)
        self.assertIn("sub/AGENTS.md", hint)
        repeat = hint_for_call(
            self.runtime, "read", "read", {"path": target}
        )
        self.assertIsNone(repeat)

    def test_explicit_guidance_read_suppresses_hint(self):
        guidance_files.ensure_pinned(self.runtime)
        target = os.path.join(self.tmp.name, "sub", "AGENTS.md")
        self.assertIsNone(
            hint_for_call(self.runtime, "read", "read", {"path": target})
        )
        other = os.path.join(self.tmp.name, "sub", "notes.txt")
        self.assertIsNone(
            hint_for_call(self.runtime, "read", "read", {"path": other})
        )

    def test_same_file_not_rehinted_via_sibling_dir(self):
        guidance_files.ensure_pinned(self.runtime)
        first = os.path.join(self.tmp.name, "sub", "a", "file.txt")
        hint = hint_for_call(self.runtime, "read", "read", {"path": first})
        self.assertIsNotNone(hint)
        self.assertIn("sub/AGENTS.md", hint)
        sibling = os.path.join(self.tmp.name, "sub", "b", "file.txt")
        self.assertIsNone(
            hint_for_call(self.runtime, "read", "read", {"path": sibling})
        )

    def test_deeper_unhinted_file_still_hinted(self):
        guidance_files.ensure_pinned(self.runtime)
        shallow = os.path.join(self.tmp.name, "sub", "other.txt")
        hint = hint_for_call(self.runtime, "read", "read", {"path": shallow})
        self.assertIsNotNone(hint)
        self.assertIn("sub/AGENTS.md", hint)
        deep = os.path.join(self.tmp.name, "sub", "deep", "other.txt")
        hint = hint_for_call(self.runtime, "read", "read", {"path": deep})
        self.assertIsNotNone(hint)
        self.assertIn("sub/deep/AGENTS.md", hint)
        again = os.path.join(self.tmp.name, "sub", "deep", "again.txt")
        self.assertIsNone(
            hint_for_call(self.runtime, "read", "read", {"path": again})
        )

    def test_build_llm_context_injects_pinned_messages(self):
        sys.path.insert(0, CORE_SCRIPTS)
        try:
            from build_llm_context import build_llm_context
        finally:
            sys.path.remove(CORE_SCRIPTS)
        from server.models.content import GenericContent
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
        )
        from server.models.message import Message, MessagePart

        trigger = Message.objects.create(
            session=self.sv.session,
            session_version=self.sv,
            role=MessageRole.USER,
        )
        MessagePart.objects.create(
            message=trigger,
            type=MessagePartType.MESSAGE,
            content=GenericContent.from_text("do the thing"),
            content_type=MessageContentType.TEXT,
        )
        query = build_llm_context(self.runtime, trigger)
        bodies = [
            part.content.get() if part.content else ""
            for qm in query.related_query_messages.all()
            for part in qm.query_message_parts.all()
        ]
        text = "\n".join(str(body) for body in bodies)
        self.assertIn("Auto-loaded workspace files", text)
        self.assertIn("## AGENTS.md\nroot rules", text)
        self.assertIn("Workspace guidance files", text)
        self.assertIn("sub/AGENTS.md", text)

