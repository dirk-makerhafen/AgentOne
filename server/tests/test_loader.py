from django.test import TestCase

from registry.loader.load_agent_manifest import load_agent_manifest
from server.tests.helpers import AgentMdTestMixin, TESTPROJECT
from server.models.enums.task_enums import TaskType


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
