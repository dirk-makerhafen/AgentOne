"""Contract tests for the single AgentOne admin tool (no DB needed)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import admin_tool as module  # noqa: E402


class StubSession:
    """Minimal session stand-in; help/dispatch errors never touch the DB."""

    def get_project(self):
        return None

    @property
    def workspace(self):
        return None


class TestAdminTool(unittest.TestCase):
    def setUp(self):
        self.session = StubSession()

    def test_help_index_lists_all_scopes(self):
        ok, result = module.admin_tool(self.session, "help", "help")
        self.assertTrue(ok)
        self.assertEqual(result["status"], "success")
        for scope in ("projects", "workspaces", "cronjobs", "agents", "skills", "workitems", "system"):
            self.assertIn(scope, result["scopes"])

    def test_every_scope_help_is_discoverable(self):
        from admin_help import HELP

        for scope in HELP:
            with self.subTest(scope=scope):
                ok, result = module.admin_tool(self.session, scope, "help")
                self.assertTrue(ok)
                self.assertEqual(result["status"], "success")
                if scope == "help":
                    self.assertIn("scopes", result)
                else:
                    self.assertIsInstance(result["actions"], dict)

    def test_unknown_scope_and_action_are_errors(self):
        ok, result = module.admin_tool(self.session, "nope", "list")
        self.assertFalse(ok)
        self.assertEqual(result["status"], "error")
        self.assertIn("Valid scopes", result["message"])

        ok, result = module.admin_tool(self.session, "projects", "nope")
        self.assertFalse(ok)
        self.assertIn("Valid", result["message"])

    def test_manifest_scopes_expose_reads_not_writes(self):
        from admin_help import HELP

        for scope in ("agents", "skills"):
            with self.subTest(scope=scope):
                self.assertIn("list", HELP[scope]["actions"])
                self.assertIn("stats", HELP[scope]["actions"])
                self.assertIn("details", HELP[scope]["actions"])
                ok, result = module.admin_tool(self.session, scope, "create")
                self.assertFalse(ok)
                self.assertIn("Unknown action", result["message"])

    def test_system_reload_is_registered(self):
        from admin_help import HELP

        self.assertIn("reload", HELP["system"]["actions"])
        ok, result = module.admin_tool(self.session, "workitems", "create")
        self.assertFalse(ok)
        self.assertIn("no state-changing actions", result["message"])

    def test_aliases_and_action_aliases(self):
        ok, result = module.admin_tool(self.session, "cronjob", "?")
        self.assertTrue(ok)
        self.assertEqual(result["scope"], "cronjobs")

    def test_schema_exposes_only_scope_and_action(self):
        from registry.loader.load_python_entry import generate_schema_for_function, _strip_bound_param

        _description, schema = generate_schema_for_function(module.admin_tool)
        _strip_bound_param(schema)
        self.assertEqual(set(schema["properties"]), {"scope", "action"})
        self.assertEqual(set(schema["required"]), {"scope", "action"})


if __name__ == "__main__":
    unittest.main()
