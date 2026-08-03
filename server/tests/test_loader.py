from django.test import TestCase

from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_chain_entry import load_chain_entry
from server.tests.helpers import AgentMdTestMixin, TESTPROJECT
from server.models.enums.task_enums import TaskType, TaskExecutionMode
from pathlib import Path


class LoaderTest(AgentMdTestMixin, TestCase):
    """Tests for ``_resolve_agent_version_tasks`` via the real loader pipeline.

    Each test loads an ``agent.md`` from the testproject through the real
    ``load_agent_manifest`` and asserts on the resulting ``task_versions`` M2M.
    """

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.base_agent, cls.base_av = cls.load_agent("base")
        cls.child_agent, cls.child_av = cls.load_agent("child")
        cls.full_agent, cls.full_av = cls.load_agent("full_settings")
        cls.scripts_agent, cls.scripts_av = cls.load_agent("with_scripts")
        cls.sub_agent, cls.sub_av = cls.load_agent("subagents_test")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def _names(self, av) -> list[str]:
        return sorted(tdv.task_definition.name for tdv in av.task_versions.all())

    def test_group_star_resolves_all_tools_in_group(self):
        names = self._names(self.base_av)
        self.assertIn("read", names)
        self.assertIn("write", names)
        self.assertIn("delete", names)
        self.assertIn("tree", names)

    def test_exact_name_resolves_command(self):
        names = self._names(self.base_av)
        self.assertIn("ping", names)

    def test_task_names_resolved_separately(self):
        names = self._names(self.base_av)
        self.assertIn("core_task", names)

    def test_only_matching_tools_included(self):
        names = self._names(self.base_av)
        for n in names:
            tdv = next(
                tdv for tdv in self.base_av.task_versions.all()
                if tdv.task_definition.name == n
            )
            if tdv.task_type == TaskType.TOOL:
                self.assertTrue(
                    tdv.task_definition.group_name in ("fs",),
                    f"tool {n} should be in allowed group",
                )

    def test_child_inherits_parent_tools_via_extends(self):
        names = self._names(self.child_av)
        self.assertIn("read", names)
        self.assertIn("write", names)
        self.assertIn("build", names)

    def test_child_merge_plus_includes_both_parent_and_own(self):
        names = self._names(self.child_av)
        self.assertIn("read", names)
        self.assertIn("build", names)

    def test_no_match_raises_exception(self):
        agent_path = TESTPROJECT / "agents" / "no_match" / "agent.md"
        with self.assertRaises(Exception) as ctx:
            load_agent_manifest(
                agent_path,
                install_repo=self.__class__._install_repo,
            )
        self.assertIn("No Task Definition found", str(ctx.exception))

    def test_does_not_contain_tools_from_wrong_group(self):
        names = self._names(self.base_av)
        self.assertNotIn("build", names)

    def test_full_settings_round_trip(self):
        s = self.full_av.agent_settings
        self.assertEqual(s.max_retries, 3)
        self.assertEqual(s.max_turns, 10)
        self.assertEqual(s.max_unattended_turns, 5)   
        self.assertEqual(s.max_history_messages, 50)
        self.assertEqual(s.scheduler_strategy, "queue")
        self.assertEqual(s.tool_call_syntax, "default")
        self.assertEqual(s.reasoning_effort, "high")
        self.assertEqual(s.priority, 5)
        self.assertTrue(s.thinking)
        self.assertEqual(s.subagentResultDelivery, "immediate")

    def test_script_loading_adds_defined_tasks(self):
        names = [
            tdv.task_definition.name
            for tdv in self.scripts_av.defined_task_versions.all()
        ]
        self.assertIn("my_tool", names)

    def test_script_loaded_tool_resolved_via_wildcard(self):
        names = self._names(self.scripts_av)
        self.assertIn("my_tool", names)

    def test_subagent_config_parsed(self):
        self.assertIn("base", self.sub_av.subagent_configs)
        self.assertEqual(
            self.sub_av.subagent_configs["base"].get("create"), "both"
        )


class LoadChainEntryTest(TestCase):
    """Error-hint quality for chain steps that reference unknown tasks."""

    def test_missing_chain_step_includes_manifest_and_available_tasks(self):
        from server.models.tasks.task_definition import TaskDefinition
        from server.models.tasks.task_definition_version import TaskDefinitionVersion

        with self.assertRaises(LookupError) as ctx:
            load_chain_entry(
                entry={"name": "my_chain", "chain": ["call_llm"]},
                commit="abc",
                task_type=TaskType.TASK,
                task_execution_mode=TaskExecutionMode.CHAIN,
                name="my_chain",
                group_name="core",
                parent_project=None,
                parent_agent=None,
                parent_skill=None,
                existing_results=[],
                manifest_path=TESTPROJECT / "scripts" / "compact" / "scripts.md",
            )
        msg = str(ctx.exception)
        self.assertIn("'call_llm'", msg)
        self.assertIn("my_chain", msg)
        self.assertIn("scripts.md", msg)


class LoadScriptsTwoPassTest(TestCase):
    """Chain steps may reference tasks defined in OTHER scripts.md files,
    regardless of alphabetical directory order (the compact/core bug)."""

    def _write_manifest(self, scripts_dir: Path, sub: str, body: str) -> None:
        d = scripts_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "scripts.md").write_text(body)

    def test_chain_in_earlier_dir_resolves_step_from_later_dir(self):
        import shutil
        import tempfile
        from pathlib import Path
        from registry.loader.load_scripts_manifest import load_scripts_manifest
        from registry.install_repo import InstallRepo

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        scripts_dir = tmp / "scripts"

        # z-core defines call_llm; a-compact references it. "a-compact"
        # sorts first, so single-pass loading would fail.
        self._write_manifest(
            scripts_dir,
            "a-compact",
            "---\ngroup: compact\ntasks:\n  - name: compact_turn\n    type: chain\n"
            "    chain: [call_llm]\n---\n",
        )
        self._write_manifest(
            scripts_dir,
            "z-core",
            "---\ngroup: core\ntasks:\n  - name: call_llm\n"
            "    file: dummy.py\n    function: dummy\n---\n",
        )
        (scripts_dir / "z-core" / "dummy.py").write_text(
            "def dummy():\n    return 1\n"
        )

        repo = InstallRepo(repo_path=tmp / "install")
        repo.source_root = scripts_dir
        repo.sync()

        results = load_scripts_manifest(scripts_dir, install_repo=repo)
        names = {td.name for td, _ in results}
        self.assertIn("compact_turn", names)
        self.assertIn("call_llm", names)

        chain_tdv = next(tdv for _, tdv in results if _.name == "compact_turn")
        child_names = {c.task_definition.name for c in chain_tdv.child_tasks.all()}
        self.assertIn("call_llm", child_names)

    def test_truly_missing_step_raises_aggregate_error(self):
        import shutil
        import tempfile
        from pathlib import Path
        from registry.loader.load_scripts_manifest import load_scripts_manifest
        from registry.install_repo import InstallRepo

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        scripts_dir = tmp / "scripts"

        self._write_manifest(
            scripts_dir,
            "a-compact",
            "---\ngroup: compact\ntasks:\n  - name: compact_turn\n    type: chain\n"
            "    chain: [does_not_exist]\n---\n",
        )

        repo = InstallRepo(repo_path=tmp / "install")
        repo.source_root = scripts_dir
        repo.sync()

        with self.assertRaises(LookupError) as ctx:
            load_scripts_manifest(scripts_dir, install_repo=repo)
        msg = str(ctx.exception)
        self.assertIn("missing step(s)", msg)
        self.assertIn("does_not_exist", msg)
