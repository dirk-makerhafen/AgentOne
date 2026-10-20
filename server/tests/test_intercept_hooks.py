"""Tests for per-call intercept hooks (``hooks:`` ``before:``/``after:`` entries).

Covers loader validation/normalization, the ``match:`` filter evaluation in
``runtime.hooks``, and the ``AgentTaskCall.create()`` wiring for inline
(blocking) and detached ``before`` hooks.
"""
from django.test import SimpleTestCase, TestCase

from registry.loader.load_agent_manifest import _validate_hooks
from runtime import hooks as hookmod
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_instance import TaskInstance
from server.tests.helpers import AgentMdTestMixin


class InterceptLoaderTest(AgentMdTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("hooks_intercept")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_intercept_entries_stored_normalized(self):
        self.assertEqual(
            self.av.hooks,
            [
                {
                    "name": "guard-read",
                    "before": "core_task",
                    "match": {"name": "read", "type": "TOOL"},
                    "mode": "inline",
                    "on_error": "fail_closed",
                },
                {
                    "name": "trace-read",
                    "before": "core_task",
                    "match": {"name": "read", "type": "TOOL"},
                    "mode": "detached",
                    "on_error": "fail_open",
                },
                {
                    "name": "audit-write",
                    "after": "core_task",
                    "match": {"name": "write*"},
                    "mode": "detached",
                    "on_error": "fail_open",
                },
            ],
        )

    def test_lifecycle_keys_rejected(self):
        # Lifecycle events were removed: on:/task:/matcher: are unknown keys.
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "distill_turn"}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks([{"task": "distill_turn"}], "a")

    def test_mode_defaults(self):
        before = _validate_hooks([{"before": "t"}], "a")[0]
        self.assertEqual(before["mode"], "inline")
        self.assertEqual(before["on_error"], "fail_closed")
        self.assertEqual(before["match"], {})
        self.assertEqual(before["name"], "t")
        after = _validate_hooks([{"after": "t"}], "a")[0]
        self.assertEqual(after["mode"], "detached")
        self.assertEqual(after["on_error"], "fail_open")

    def test_match_list_and_type_normalization(self):
        entries = _validate_hooks(
            [{"before": "t", "match": {"session": ["main-*", "scratch"], "type": "tool"}}], "a"
        )
        self.assertEqual(
            entries[0]["match"], {"session": "main-* | scratch", "type": "TOOL"}
        )

    def test_session_type_normalization(self):
        entries = _validate_hooks(
            [{"after": "t", "match": {"session_type": ["SESSION", "Subtask_Fork"]}}], "a"
        )
        self.assertEqual(entries[0]["match"], {"session_type": "session | subtask_fork"})

    def test_rejects_agent_dimension(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"before": "t", "match": {"agent": "a1"}}], "a")

    def test_rejects_before_and_after(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"before": "a", "after": "b"}], "a")

    def test_rejects_on_with_before(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "before": "a"}], "a")

    def test_rejects_missing_target(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"match": {"name": "x"}}], "a")

    def test_rejects_inline_before_fail_open(self):
        with self.assertRaises(ValueError):
            _validate_hooks(
                [{"before": "t", "mode": "inline", "on_error": "fail_open"}], "a"
            )

    def test_rejects_timeout_on_intercept(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"before": "t", "timeout_seconds": 30}], "a")

    def test_rejects_bad_mode_type_and_keys(self):
        with self.assertRaises(ValueError):
            _validate_hooks([{"before": "t", "mode": "blocking"}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks(
                [{"before": "t", "match": {"type": "nope"}}], "a"
            )
        with self.assertRaises(ValueError):
            _validate_hooks(
                [{"before": "t", "match": {"bogus": "x"}}], "a"
            )
        with self.assertRaises(ValueError):
            _validate_hooks([{"after": "t", "task": "x"}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "before": "y"}], "a")
        with self.assertRaises(ValueError):
            _validate_hooks([{"on": "stop", "task": "x", "mode": "inline"}], "a")


class InterceptMatcherTest(SimpleTestCase):
    def test_wildcard_match_all(self):
        self.assertTrue(
            hookmod.matches_call_hook(
                {"before": "t"}, def_name="anything", def_type="TOOL",
                session_name="s",
            )
        )

    def test_name_glob_and_alternation(self):
        entry = {"before": "t", "match": {"name": "read* | write*"}}
        self.assertTrue(hookmod.matches_call_hook(entry, def_name="read"))
        self.assertTrue(hookmod.matches_call_hook(entry, def_name="write-file"))
        self.assertFalse(hookmod.matches_call_hook(entry, def_name="delete"))

    def test_type_case_insensitive(self):
        entry = {"after": "t", "match": {"type": "TOOL"}}
        self.assertTrue(hookmod.matches_call_hook(entry, def_name="x", def_type="tool"))
        self.assertFalse(hookmod.matches_call_hook(entry, def_name="x", def_type="TASK"))

    def test_session_and_logic(self):
        entry = {
            "before": "t",
            "match": {"name": "read*", "session": "foobar23*"},
        }
        self.assertTrue(
            hookmod.matches_call_hook(
                entry, def_name="read", session_name="foobar23chat"
            )
        )
        self.assertFalse(
            hookmod.matches_call_hook(
                entry, def_name="write", session_name="foobar23chat"
            )
        )
        self.assertFalse(
            hookmod.matches_call_hook(
                entry, def_name="read", session_name="other"
            )
        )

    def test_session_type_match(self):
        entry = {
            "after": "t",
            "match": {"name": "session_end", "session_type": "session | subsession"},
        }
        self.assertTrue(
            hookmod.matches_call_hook(entry, def_name="session_end", session_type="session")
        )
        self.assertTrue(
            hookmod.matches_call_hook(entry, def_name="session_end", session_type="SUBSESSION")
        )
        for excluded in ("subtask_fork", "subtask_delegate", "subtask_compaction", "subtask_hook"):
            self.assertFalse(
                hookmod.matches_call_hook(
                    entry, def_name="session_end", session_type=excluded
                )
            )

    def test_lifecycle_entry_never_matches(self):
        self.assertFalse(
            hookmod.matches_call_hook(
                {"on": "stop", "task": "t"}, def_name="t"
            )
        )

    def test_recursion_guard(self):
        entries = [
            {"name": "g", "before": "guard", "match": {"name": "*"}},
        ]
        ctx = {"def_name": "guard", "def_type": "TOOL", "session_name": "s"}
        self.assertEqual(hookmod.matching_intercepts(entries, "before", ctx), [])
        ctx = {"def_name": "other", "def_type": "TOOL", "session_name": "s"}
        self.assertEqual(len(hookmod.matching_intercepts(entries, "before", ctx)), 1)

    def test_intercept_entries_and_names(self):
        entries = [
            {"name": "a", "before": "t1"},
            {"name": "b", "after": "t2"},
            {"name": "c", "on": "stop", "task": "t3"},
        ]
        self.assertEqual(len(hookmod.intercept_entries(entries, "before")), 1)
        self.assertEqual(len(hookmod.intercept_entries(entries, "after")), 1)
        self.assertEqual(hookmod.hook_task_names(entries), {"t1", "t2"})


class InterceptWiringTest(AgentMdTestMixin, TestCase):
    """``AgentTaskCall.create()`` chains inline ``before`` hooks and stashes
    detached ones without dispatching (no scheduler involvement)."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()
        cls.agent, cls.av = cls.load_agent("hooks_intercept")

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def _task_instance(self, session_version, task_name):
        tdv = TaskDefinition.objects.get(name=task_name).latest_task_version
        return TaskInstance.get_or_create(
            task_definition=tdv, session_version=session_version
        )

    def test_inline_before_chains_and_detached_stashed(self):
        session = self.create_session(self.agent, self.av)
        sv = session.latest_session_version
        ti = self._task_instance(sv, "read")
        call = AgentTaskCall.create(task_instance=ti, kwargs={"path": "x"})
        inline = list(call.taskcall_before_run_hooks.all())
        self.assertEqual(len(inline), 1)
        self.assertEqual(inline[0].task_definition.name, "core_task")
        detached = getattr(call, "_detached_intercept_calls", [])
        self.assertEqual(len(detached), 1)
        self.assertEqual(detached[0].task_definition.name, "core_task")

    def test_unmatched_call_gets_no_hooks(self):
        session = self.create_session(self.agent, self.av)
        sv = session.latest_session_version
        ti = self._task_instance(sv, "delete")
        call = AgentTaskCall.create(task_instance=ti, kwargs={})
        self.assertEqual(call.taskcall_before_run_hooks.count(), 0)
        self.assertEqual(getattr(call, "_detached_intercept_calls", []), [])

    def test_hook_task_call_does_not_refire(self):
        session = self.create_session(self.agent, self.av)
        sv = session.latest_session_version
        ti = self._task_instance(sv, "core_task")
        call = AgentTaskCall.create(task_instance=ti, kwargs={})
        self.assertEqual(call.taskcall_before_run_hooks.count(), 0)
        self.assertEqual(getattr(call, "_detached_intercept_calls", []), [])

    def test_framework_fork_session_fires_nothing(self):
        from server.models.sessions.session import SessionModel

        session = self.create_session(self.agent, self.av)
        SessionModel.objects.filter(pk=session.pk).update(
            session_type="subtask_hook"
        )
        session.refresh_from_db()
        sv = session.latest_session_version
        ti = self._task_instance(sv, "read")
        call = AgentTaskCall.create(task_instance=ti, kwargs={"path": "x"})
        self.assertEqual(call.taskcall_before_run_hooks.count(), 0)
        self.assertEqual(getattr(call, "_detached_intercept_calls", []), [])
