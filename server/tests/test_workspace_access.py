"""Tests for workspace filesystem access policy (runtime/workspace_access.py).

Uses SimpleTestCase (no DB) — policy resolution works against lightweight
stand-in session/workspace objects.
"""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from runtime.workspace_access import (
    evaluate,
    extract_path_args,
    resolve_policy,
    task_access_posture,
    validate_agent_access,
    validate_workspace_access,
)


class _Agent:
    def __init__(self, access: dict | None = None):
        self._access = access

    def get_agent_setting(self, name: str):
        if name == "extra_settings" and self._access is not None:
            return {"access": self._access}
        return None


class _Session:
    def __init__(self, root: Path, access: dict | None = None, agent_access: dict | None = None):
        self.workspace = type(
            "WS", (), {"path": root.as_posix(), "access": access or {}}
        )()
        self.agent = _Agent(agent_access)


class WorkspaceAccessEvaluateTest(SimpleTestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)
        (self.root / "inbox").mkdir()
        (self.root / "secrets").mkdir()
        (self.root / "docs").mkdir()

    def test_inside_read_allowed_by_default(self):
        policy = resolve_policy(_Session(self.root))
        self.assertEqual(evaluate(policy, str(self.root / "a.md"), "read").action, "allow")

    def test_no_workspace_allows_everything(self):
        class NoWS:
            workspace = None
            agent = _Agent()

        policy = resolve_policy(NoWS())
        self.assertEqual(evaluate(policy, "/etc/hosts", "read").action, "allow")
        self.assertEqual(evaluate(policy, "/etc/hosts", "write").action, "allow")

    def test_write_default_deny_read_only_workspace(self):
        session = _Session(self.root, access={
            "write": {"default": "deny"},
        })
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, str(self.root / "a.md"), "write").action, "deny")
        self.assertEqual(evaluate(policy, str(self.root / "a.md"), "read").action, "allow")

    def test_write_carveout_allow(self):
        session = _Session(self.root, access={
            "write": {"default": "deny", "allow": ["inbox/**"]},
        })
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, str(self.root / "inbox" / "f.md"), "write").action, "allow")
        self.assertEqual(evaluate(policy, str(self.root / "docs" / "f.md"), "write").action, "deny")

    def test_workspace_relative_deny(self):
        session = _Session(self.root, access={
            "read": {"default": "allow", "deny": ["**/*.env", "secrets/**"]},
        })
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, str(self.root / "sub" / "x.env"), "read").action, "deny")
        self.assertEqual(evaluate(policy, str(self.root / "secrets" / "k"), "read").action, "deny")
        self.assertEqual(evaluate(policy, str(self.root / "docs" / "a.md"), "read").action, "allow")

    def test_ask_precedence_over_allow(self):
        session = _Session(self.root, access={
            "write": {
                "default": "deny",
                "allow": ["inbox/**"],
                "ask": ["inbox/*.tmp"],
            },
        })
        policy = resolve_policy(session)
        self.assertEqual(
            evaluate(policy, str(self.root / "inbox" / "x.tmp"), "write").action, "ask"
        )
        self.assertEqual(
            evaluate(policy, str(self.root / "inbox" / "x.md"), "write").action, "allow"
        )

    def test_global_deny_wins_across_scopes(self):
        # Workspace deny applies even to external paths.
        session = _Session(self.root, access={
            "read": {"default": "allow", "deny": ["**/*.env"]},
        })
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, "/tmp/other/.env", "read").action, "deny")
        self.assertEqual(evaluate(policy, "/tmp/other/file.txt", "read").action, "deny")

    def test_external_deny_by_default(self):
        session = _Session(self.root, access={
            "read": {"default": "allow"},
            "write": {"default": "deny"},
        })
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, "/etc/hosts", "read").action, "deny")
        self.assertEqual(evaluate(policy, "/etc/hosts", "write").action, "deny")

    def test_external_allow_via_agent(self):
        session = _Session(
            self.root,
            access={"read": {"default": "allow"}, "write": {"default": "deny"}},
            agent_access={
                "external": {
                    "read": {"default": "deny", "allow": ["/tmp/shared/**"]},
                    "write": {"default": "deny"},
                }
            },
        )
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, "/tmp/shared/a.md", "read").action, "allow")
        self.assertEqual(evaluate(policy, "/etc/hosts", "read").action, "deny")
        self.assertEqual(evaluate(policy, "/tmp/shared/a.md", "write").action, "deny")

    def test_agent_workspace_override_tightens_default(self):
        session = _Session(
            self.root,
            access={"read": {"default": "allow"}, "write": {"default": "allow"}},
            agent_access={
                "workspace": {"write": {"default": "deny"}},
            },
        )
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, str(self.root / "a.md"), "write").action, "deny")

    def test_agent_write_implies_read(self):
        # A path allowed for writes is also readable even when reads deny.
        session = _Session(
            self.root,
            access={"read": {"default": "deny"}, "write": {"default": "deny"}},
            agent_access={
                "external": {
                    "write": {"default": "deny", "allow": ["/tmp/out/**"]},
                }
            },
        )
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, "/tmp/out/f.md", "write").action, "allow")
        self.assertEqual(evaluate(policy, "/tmp/out/f.md", "read").action, "allow")

    def test_read_rules_never_grant_write(self):
        session = _Session(
            self.root,
            access={"read": {"default": "deny"}, "write": {"default": "deny"}},
            agent_access={
                "external": {
                    "read": {"default": "deny", "allow": ["/tmp/readonly/**"]},
                }
            },
        )
        policy = resolve_policy(session)
        self.assertEqual(evaluate(policy, "/tmp/readonly/f.md", "read").action, "allow")
        self.assertEqual(evaluate(policy, "/tmp/readonly/f.md", "write").action, "deny")


class WorkspaceAccessGlobTest(SimpleTestCase):
    def test_symlink_resolution_variant(self):
        # /tmp may resolve to /private/tmp on macOS — both forms must match.
        from runtime.workspace_access import _matches

        self.assertTrue(
            _matches(["/tmp/shared/**"], ["/tmp/shared/a.md", "/private/tmp/shared/a.md"], None)
        )

    def test_relative_pattern_matches_workspace_relative(self):
        from runtime.workspace_access import _matches

        self.assertTrue(_matches(["secrets/**"], ["/var/x/secrets/k"], "secrets/k"))


class ExtractPathArgsTest(SimpleTestCase):
    def test_read_tool(self):
        result = extract_path_args("read", "read", {"path": "/a/b.md"})
        self.assertEqual(result, [("/a/b.md", "read")])

    def test_write_tool_multiple_paths(self):
        result = extract_path_args(
            "copy", "write", {"source": "/a", "destination": "/b"}
        )
        self.assertEqual(result, [("/a", "write"), ("/b", "write")])

    def test_no_posture_ignored(self):
        self.assertEqual(extract_path_args("shell", None, {"source": "x"}), [])

    def test_non_string_path_ignored(self):
        self.assertEqual(extract_path_args("write", "write", {"path": 42}), [])


class TaskAccessPostureTest(SimpleTestCase):
    def _td(self, posture=None, group=""):
        return type("TD", (), {"access_posture": posture, "group_name": group})()

    def test_manifest_field_wins(self):
        td = self._td(posture="write", group="something-else")
        self.assertEqual(task_access_posture(td), "write")

    def test_fallback_to_group(self):
        self.assertEqual(task_access_posture(self._td(group="filesystem-read")), "read")
        self.assertEqual(task_access_posture(self._td(group="filesystem-write")), "write")

    def test_unknown_returns_none(self):
        self.assertIsNone(task_access_posture(self._td(group="execution")))
        self.assertIsNone(task_access_posture(self._td()))


class AccessValidationTest(SimpleTestCase):
    def test_valid_workspace_access(self):
        validate_workspace_access(
            {"read": {"default": "allow", "deny": ["secrets/**"]}, "write": {"default": "deny"}}
        )

    def test_workspace_denies_absolute_pattern(self):
        with self.assertRaises(ValueError):
            validate_workspace_access({"read": {"deny": ["/etc/**"]}})

    def test_workspace_denies_tilde_pattern(self):
        with self.assertRaises(ValueError):
            validate_workspace_access({"read": {"deny": ["~/secrets/**"]}})

    def test_workspace_denies_dotdot(self):
        with self.assertRaises(ValueError):
            validate_workspace_access({"write": {"allow": ["../shared/**"]}})

    def test_agent_external_requires_absolute(self):
        with self.assertRaises(ValueError):
            validate_agent_access({"external": {"read": {"allow": ["shared/**"]}}})

    def test_agent_external_accepts_tilde(self):
        validate_agent_access({"external": {"read": {"allow": ["~/shared/**"]}}})

    def test_agent_workspace_scope_relative_only(self):
        validate_agent_access({"workspace": {"write": {"deny": ["secrets/**"]}}})
        with self.assertRaises(ValueError):
            validate_agent_access({"workspace": {"write": {"deny": ["/abs/**"]}}})

    def test_invalid_default_posture(self):
        with self.assertRaises(ValueError):
            validate_workspace_access({"read": {"default": "banana"}})

    def test_invalid_shape(self):
        with self.assertRaises(ValueError):
            validate_workspace_access("nope")


class BoundTaskFilesystemBlockTest(SimpleTestCase):
    """bound_task._filesystem_access_block short-circuits deny verdicts.

    No DB is required: the block helper only touches the session wrapper and
    task definition metadata, which we fake here.
    """

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)

    def _make_task(self, group_name: str, name: str, arg_names: list[str],
                   execution_mode: str = "python"):
        td = type("TD", (), {"group_name": group_name, "name": name})()
        tdv = type(
            "TDV",
            (),
            {"arg_names": arg_names, "task_execution_mode": execution_mode},
        )()
        return td, tdv

    def _make_bound_task(self, td, tdv, session):
        from runtime.tasks.bound_task import BoundTask

        bt = BoundTask.__new__(BoundTask)
        bt.task_definition = td
        bt.task_definition_version = tdv
        bt.session = session
        return bt

    def test_write_to_denied_path_blocked(self):
        from runtime.tasks.bound_task import BoundTask

        td, tdv = self._make_task("filesystem-write", "write", ["path"])
        session = _Session(
            self.root,
            access={"write": {"default": "allow", "deny": ["**/*.env"]}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(path=str(self.root / "secret.env"))
        self.assertIsNotNone(reason)
        self.assertIn("denied", reason.lower())

    def test_allowed_inside_path_not_blocked(self):
        td, tdv = self._make_task("filesystem-write", "write", ["path"])
        session = _Session(
            self.root,
            access={"write": {"default": "allow", "deny": ["**/*.env"]}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(path=str(self.root / "ok.txt"))
        self.assertIsNone(reason)

    def test_external_deny_blocked(self):
        td, tdv = self._make_task("filesystem-write", "write", ["path"])
        session = _Session(
            self.root,
            access={"write": {"default": "allow"}},
            agent_access={"external": {"write": {"default": "deny"}}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(path="/tmp/outside.txt")
        self.assertIsNotNone(reason)
        self.assertIn("outside", reason.lower())

    def test_shell_write_outside_blocked(self):
        td, tdv = self._make_task("execution", "shell", ["source"])
        session = _Session(
            self.root,
            access={"write": {"default": "deny"}},
            agent_access={"external": {"write": {"default": "deny"}}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(source="echo hi > /tmp/out.txt")
        self.assertIsNotNone(reason)
        self.assertIn("blocked", reason.lower())

    def test_shell_read_outside_blocked_by_external_default(self):
        td, tdv = self._make_task("execution", "shell", ["source"])
        session = _Session(
            self.root,
            access={"write": {"default": "deny"}},
            agent_access={"external": {"read": {"default": "deny"}}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(source="cat /etc/passwd")
        self.assertIsNotNone(reason)

    def test_shell_inside_allowed(self):
        td, tdv = self._make_task("execution", "shell", ["source"])
        session = _Session(
            self.root,
            access={"write": {"default": "allow"}},
        )
        bt = self._make_bound_task(td, tdv, session)
        reason = bt._filesystem_access_block(source=f"echo hi > {self.root}/in.txt")
        self.assertIsNone(reason)

    def test_call_blocks_script_mode_before_execution(self):
        """SCRIPT-mode tools must be blocked before the binary runs.

        Regression: the access check used to live only in the Python-function
        path, after the SCRIPT early-return, so script tools bypassed the policy.
        """
        td, tdv = self._make_task(
            "filesystem-write", "write", ["path"], execution_mode="SCRIPT"
        )
        session = _Session(
            self.root,
            access={"write": {"default": "allow"}},
            agent_access={"external": {"write": {"default": "deny"}}},
        )
        bt = self._make_bound_task(td, tdv, session)

        executed: list[str] = []
        bt._call_script = lambda *a, **k: executed.append("ran")  # pragma: no cover

        result = bt.call(path="/tmp/outside.txt")
        self.assertFalse(result[0])
        self.assertEqual(result[1]["status"], "error")
        self.assertEqual(result[1]["return_code"], -1)
        self.assertIn("blocked", result[1]["stderr"].lower())
        self.assertEqual(executed, [])

    def test_call_allows_script_mode_when_not_blocked(self):
        """SCRIPT-mode tools still execute when the policy allows."""
        from unittest.mock import patch

        td, tdv = self._make_task(
            "filesystem-write", "write", ["path"], execution_mode="SCRIPT"
        )
        session = _Session(
            self.root,
            access={"write": {"default": "allow"}},
        )
        bt = self._make_bound_task(td, tdv, session)
        bt._call_script = lambda *a, **k: (True, {"status": "success"})

        with patch.object(
            bt, "_runtime_file_name", return_value="tool.py"
        ), patch("runtime.tasks.bound_task.RuntimeFolder"):
            result = bt.call(path=str(self.root / "ok.txt"))
        self.assertEqual(result, (True, {"status": "success"}))
