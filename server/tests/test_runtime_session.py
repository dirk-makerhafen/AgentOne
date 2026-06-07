from django.test import TestCase

from server.models.settings import SettingsModel
from server.tests.helpers import AgentMdTestMixin


class RuntimeSessionTest(AgentMdTestMixin, TestCase):
    """Tests for the ``Session`` runtime wrapper using real loaded agents.

    Verifies that session-level disallowed overlays correctly compose with
    agent-level disallowed, and that the merge (``+``) and full-override
    semantics work correctly.
    """

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.base_agent, cls.base_av = cls.load_agent("base")
        cls.disallowed_agent, cls.disallowed_av = cls.load_agent("disallowed")
        cls.cmds_agent, cls.cmds_av = cls.load_agent("disallowed_cmds")
        cls.so_agent, cls.so_av = cls.load_agent("session_override")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _session(self, agent_model, agent_version, session_settings=None):
        session = self.create_session(
            agent_model, agent_version,
            session_settings=session_settings,
        )
        return session.get_runtime()

    # ------------------------------------------------------------------
    # Inherited agent disallowed
    # ------------------------------------------------------------------

    def test_inherits_agent_disallowed(self):
        session = self._session(
            self.disallowed_agent, self.disallowed_av,
        )
        names = session.allowedToolNames
        self.assertIn("read", names)
        self.assertIn("write", names)
        self.assertNotIn("delete", names)

    # ------------------------------------------------------------------
    # Session adds disallowed on top
    # ------------------------------------------------------------------

    def test_session_extra_disallowed(self):
        settings = SettingsModel.objects.create(
            disallowedToolNames=["write"],
        )
        session = self._session(
            self.disallowed_agent, self.disallowed_av,
            session_settings=settings,
        )
        names = session.allowedToolNames
        self.assertIn("read", names)
        self.assertNotIn("write", names)

    def test_get_tool_returns_none_for_session_disallowed(self):
        settings = SettingsModel.objects.create(
            disallowedToolNames=["read"],
        )
        session = self._session(
            self.base_agent, self.base_av,
            session_settings=settings,
        )
        self.assertIsNone(session.get_tool("read"))
        self.assertIsNotNone(session.get_tool("write"))

    # ------------------------------------------------------------------
    # Session-level disallowed commands and tasks
    # ------------------------------------------------------------------

    def test_session_disallowed_commands(self):
        settings = SettingsModel.objects.create(
            disallowedCommandNames=["ping"],
        )
        session = self._session(
            self.base_agent, self.base_av,
            session_settings=settings,
        )
        self.assertNotIn("ping", session.allowedCommandNames)
        self.assertIsNone(session.get_command("ping"))

    def test_session_disallowed_tasks(self):
        settings = SettingsModel.objects.create(
            disallowedTaskNames=["core_task"],
        )
        session = self._session(
            self.base_agent, self.base_av,
            session_settings=settings,
        )
        self.assertNotIn("core_task", session.allowedTaskNames)
        self.assertIsNone(session.get_task("core_task"))

    # ------------------------------------------------------------------
    # Tools-only agent (session_override) with session overrides
    # ------------------------------------------------------------------

    def test_tools_only_session_allowed_tools(self):
        session = self._session(self.so_agent, self.so_av)
        names = session.allowedToolNames
        self.assertIn("read", names)
        self.assertIn("write", names)
        self.assertNotIn("nonexistent", names)

    def test_tools_only_session_no_commands_or_tasks(self):
        session = self._session(self.so_agent, self.so_av)
        self.assertEqual(session.allowedCommandNames, [])
        self.assertEqual(session.allowedTaskNames, [])

    def test_tools_only_session_extra_disallowed(self):
        settings = SettingsModel.objects.create(
            disallowedToolNames=["delete"],
        )
        session = self._session(
            self.so_agent, self.so_av,
            session_settings=settings,
        )
        names = session.allowedToolNames
        self.assertIn("read", names)
        self.assertNotIn("delete", names)

    def test_tools_only_session_get_tool_none_for_disallowed(self):
        settings = SettingsModel.objects.create(
            disallowedToolNames=["read"],
        )
        session = self._session(
            self.so_agent, self.so_av,
            session_settings=settings,
        )
        self.assertIsNone(session.get_tool("read"))
        self.assertIsNotNone(session.get_tool("write"))
