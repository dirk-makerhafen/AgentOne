from django.test import TestCase

from runtime.agents.agent import Agent
from server.tests.helpers import AgentMdTestMixin


class RuntimeAgentTest(AgentMdTestMixin, TestCase):
    """Tests for the ``Agent`` runtime wrapper using real loaded agents."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.base_agent, cls.base_av = cls.load_agent("base")
        cls.disallowed_agent, cls.disallowed_av = cls.load_agent("disallowed")
        cls.full_agent, cls.full_av = cls.load_agent("full_settings")
        cls.disallowed_cmds_agent, cls.disallowed_cmds_av = cls.load_agent(
            "disallowed_cmds"
        )
        cls.sub_agent, cls.sub_av = cls.load_agent("subagents_test")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _agent(self, agent_model):
        return Agent(agent_model=agent_model)

    # ------------------------------------------------------------------
    # Scalar settings
    # ------------------------------------------------------------------

    def test_max_retries(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.max_retries, 3)

    def test_max_turns(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.max_turns, 10)

    def test_max_unattended_turns(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.max_unattended_turns, 5)

    def test_max_history_messages(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.max_history_messages, 50)

    def test_scheduler_strategy(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.scheduler_strategy, "queue")

    def test_tool_call_syntax(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.tool_call_syntax, "default")

    def test_reasoning_effort(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.reasoning_effort, "high")

    def test_priority(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.priority, 5)

    def test_thinking(self):
        agent = self._agent(self.full_agent)
        self.assertTrue(agent.get_agent_setting("thinking"))

    def test_subagent_result_delivery(self):
        agent = self._agent(self.full_agent)
        self.assertEqual(agent.subagentResultDelivery, "immediate")

    def test_system_prompt(self):
        agent = self._agent(self.full_agent)
        self.assertIn("scalar settings", agent.system_prompt)

    # ------------------------------------------------------------------
    # allowedToolNames
    # ------------------------------------------------------------------

    def test_allowed_tool_names_returns_concrete_names(self):
        agent = self._agent(self.base_agent)
        names = agent.allowedToolNames
        self.assertIn("read", names)
        self.assertIn("write", names)

    def test_allowed_tool_names_excludes_disallowed_exact(self):
        agent = self._agent(self.disallowed_agent)
        self.assertNotIn("delete", agent.allowedToolNames)

    def test_allowed_tool_names_excludes_disallowed_wildcard(self):
        agent = self._agent(self.disallowed_agent)
        self.assertNotIn("tree", agent.allowedToolNames)

    def test_allowed_tool_names_includes_non_disallowed(self):
        agent = self._agent(self.disallowed_agent)
        self.assertIn("read", agent.allowedToolNames)
        self.assertIn("write", agent.allowedToolNames)
        self.assertIn("build", agent.allowedToolNames)

    # ------------------------------------------------------------------
    # allowedTools  (returns TaskDefinitionVersion objects)
    # ------------------------------------------------------------------

    def test_allowed_tools_returns_filtered_tdv_objects(self):
        agent = self._agent(self.disallowed_agent)
        tools = agent.allowedTools
        names = [tdv.task_definition.name for tdv in tools]
        self.assertIn("read", names)
        self.assertNotIn("delete", names)

    # ------------------------------------------------------------------
    # get_tool
    # ------------------------------------------------------------------

    def test_get_tool_returns_tdv_for_allowed(self):
        agent = self._agent(self.base_agent)
        tdv = agent.get_tool("read")
        self.assertIsNotNone(tdv)
        self.assertEqual(tdv.task_definition.name, "read")

    def test_get_tool_returns_none_for_disallowed(self):
        agent = self._agent(self.disallowed_agent)
        self.assertIsNone(agent.get_tool("delete"))

    def test_get_tool_returns_none_for_nonexistent(self):
        agent = self._agent(self.base_agent)
        self.assertIsNone(agent.get_tool("nonexistent"))

    # ------------------------------------------------------------------
    # Tasks and commands
    # ------------------------------------------------------------------

    def test_allowed_task_names(self):
        agent = self._agent(self.base_agent)
        self.assertIn("core_task", agent.allowedTaskNames)

    def test_allowed_command_names(self):
        agent = self._agent(self.base_agent)
        self.assertIn("ping", agent.allowedCommandNames)

    def test_disallowed_command_excluded(self):
        agent = self._agent(self.disallowed_cmds_agent)
        self.assertIn("ping", agent.allowedCommandNames)
        self.assertNotIn("pong", agent.allowedCommandNames)

    def test_get_command_returns_none_for_disallowed(self):
        agent = self._agent(self.disallowed_cmds_agent)
        self.assertIsNotNone(agent.get_command("ping"))
        self.assertIsNone(agent.get_command("pong"))

    def test_disallowed_task_wildcard_empties_allowed(self):
        agent = self._agent(self.disallowed_cmds_agent)
        # disallowedTasks: [core.*] should exclude core_task
        self.assertNotIn("core_task", agent.allowedTaskNames)

    def test_get_task_returns_none_for_disallowed(self):
        agent = self._agent(self.disallowed_cmds_agent)
        self.assertIsNone(agent.get_task("core_task"))

    # ------------------------------------------------------------------
    # Subagents
    # ------------------------------------------------------------------

    def test_subagent_config(self):
        agent = self._agent(self.sub_agent)
        cfg = agent.subagent_config("base")
        self.assertEqual(cfg.get("create"), "both")

    def test_subagent_names(self):
        agent = self._agent(self.sub_agent)
        self.assertIn("base", agent.subagentNames)
