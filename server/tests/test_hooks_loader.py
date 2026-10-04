"""Loader tests for agent.md ``hooks:`` (see ``docs/session-hooks.md`` §10)."""
from django.test import TestCase

from registry.loader.load_agent_manifest import _validate_hooks
from runtime.agents.agent import Agent
from server.tests.helpers import AgentMdTestMixin


class LoadHooksTest(AgentMdTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.ok_agent, cls.ok_av = cls.load_agent("hooks_ok")
        cls.child_agent, cls.child_av = cls.load_agent("hooks_child")
        cls.base_agent, cls.base_av = cls.load_agent("base")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_hooks_parsed_and_stored(self):
        self.assertEqual(
            self.ok_av.hooks,
            [
                {
                    "name": "reflect",
                    "on": "stop",
                    "matcher": "session",
                    "task": "distill_turn",
                    "ingest": "record_memory",
                    "max_tokens": 10000,
                    "timeout_seconds": 60,
                },
                {
                    "name": "archive_transcript",
                    "on": "post_compact",
                    "task": "archive_transcript",
                    "max_tokens": 40000,
                    "timeout_seconds": 300,
                },
                {
                    "name": "write_journal",
                    "on": "session_end",
                    "task": "write_journal",
                    "max_tokens": 40000,
                    "timeout_seconds": 120,
                },
            ],
        )

    def test_hooks_merge_through_extends(self):
        agent = Agent(agent_model=self.child_agent)
        self.assertEqual(
            [(h["on"], h["name"], h["task"]) for h in agent.hooks],
            [
                ("stop", "reflect", "distill_turn_v2"),  # overridden
                ("session_end", "idle-watch", "write_journal"),  # added
                ("post_compact", "archive_transcript", "archive_transcript"),  # inherited
                ("session_end", "write_journal", "write_journal"),  # inherited
            ],
        )

    def test_no_hooks_is_empty_list(self):
        self.assertEqual(self.base_av.hooks, [])
        self.assertEqual(Agent(agent_model=self.base_agent).hooks, [])

    def test_validate_rejects_bad_on(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "every_tea_time", "task": "x"}], "a")

    def test_validate_rejects_missing_task(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop"}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "  "}], "a")

    def test_validate_rejects_blocking(self):
        with self.assertRaises(ValueError):
            _validate_hooks(
                [{"on": "stop", "task": "x", "blocking": True}], "a"
            )

    def test_validate_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "sink": "file"}], "a")

    def test_validate_rejects_bad_budgets(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "max_tokens": -1}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks(
                [{"on": "stop", "task": "x", "timeout_seconds": True}], "a"
            )

    def test_validate_rejects_bad_matcher_and_agent(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "matcher": 42}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "agent": "  "}], "a")

    def test_validate_rejects_non_list(self):
        with self.assertRaises(ValueError):
            _validate_hooks({"on": "stop", "task": "x"}, "a")
        with self.assertRaises(ValueError):
            _validate_hooks(["stop"], "a")
