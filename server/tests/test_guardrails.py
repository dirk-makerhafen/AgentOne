"""Tests for the guardrail system (runtime/guardrails.py).

Uses SimpleTestCase (no DB) since all functions are pure.
"""
from pathlib import Path

from django.test import SimpleTestCase

from runtime.guardrails import (
    check_shell_command,
    check_python_command,
    lint_shell_command,
)

class CheckShellCommandTest(SimpleTestCase):
    """sh-guard based shell command safety checks."""

    def test_safe_commands_allowed(self):
        for cmd in ["ls -la", "pwd", "echo hello", "cat README.md"]:
            with self.subTest(cmd=cmd):
                v = check_shell_command(cmd)
                self.assertEqual(v.action, "allow")

    def test_risky_commands_ask_at_default_threshold(self):
        for cmd in [
            "bash a",
            "cd src",
            "source a",
        ]:
            with self.subTest(cmd=cmd):
                v = check_shell_command(cmd, ask_threshold=60)
                self.assertEqual(v.action, "ask")

    def test_critical_commands_ask(self):
        for cmd in ["rm -rf /", "cat a | bash", "cd /", "echo rm -rf / | bash"]:
            with self.subTest(cmd=cmd):
                v = check_shell_command(cmd)
                self.assertEqual(v.action, "ask")

    def test_pipeline_constructor_ask_at_lower_threshold(self):
        cmd = "echo r>a ; echo m>a ; echo  ->a  ; echo rf>a  ; echo \\ *>a  | cat a | bash"
        v = check_shell_command(cmd, ask_threshold=60)
        self.assertEqual(v.action, "ask")
        v2 = check_shell_command(cmd)
        self.assertIn(v2.action, ("allow", "ask"))

    def test_git_operations_allowed(self):
        for cmd in ["git status", "git diff", "git log --oneline -5"]:
            with self.subTest(cmd=cmd):
                v = check_shell_command(cmd)
                self.assertEqual(v.action, "allow")

    def test_high_threshold_only_blocks_critical(self):
        v = check_shell_command("rm -rf /", ask_threshold=90)
        self.assertEqual(v.action, "ask")
        v2 = check_shell_command("cd src", ask_threshold=90)
        self.assertEqual(v2.action, "allow")

    def test_verdict_contains_score_and_reason(self):
        v = check_shell_command("rm -rf /")
        self.assertIsInstance(v.score, int)
        self.assertGreater(v.score, 0)
        self.assertIn(v.level, ("safe", "caution", "danger", "critical"))
        self.assertIsInstance(v.reason, str)

    def test_empty_source_allowed(self):
        v = check_shell_command("")
        self.assertEqual(v.action, "allow")

    def test_low_threshold_asks_for_most_commands(self):
        v = check_shell_command("ls -la", ask_threshold=0)
        self.assertEqual(v.action, "ask")

    def test_very_high_threshold_allows_all_but_extreme(self):
        v = check_shell_command("rm -rf /", ask_threshold=99)
        self.assertEqual(v.action, "ask")
        v2 = check_shell_command("bash a", ask_threshold=99)
        self.assertEqual(v2.action, "allow")


class CheckPythonCommandTest(SimpleTestCase):
    """AST-based Python code safety checks."""

    def test_safe_code_allowed(self):
        for code in [
            'print("hello")',
            "x = 1 + 2",
            "import math; print(math.pi)",
            "from datetime import datetime; datetime.now()",
            "import json; json.dumps({'a': 1})",
            "import sys; sys.exit(0)",
        ]:
            with self.subTest(code=code):
                v = check_python_command(code)
                self.assertEqual(v.action, "allow")

    def test_eval_exec_ask(self):
        for code in ['eval("1+1")', 'exec("print(1)")']:
            with self.subTest(code=code):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_shell_execution_ask(self):
        tests = [
            ('import os; os.system("ls")', "os.system"),
            ('import os; os.popen("ls")', "os.popen"),
            ('import subprocess; subprocess.run("cmd")', "subprocess.run"),
            ('import subprocess; subprocess.Popen("cmd")', "subprocess.Popen"),
            ('from os import system; system("ls")', "from os import system"),
        ]
        for code, label in tests:
            with self.subTest(label=label):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_file_deletion_ask(self):
        tests = [
            ('import os; os.remove("file")', "os.remove"),
            ('import os; os.unlink("file")', "os.unlink"),
            ('import shutil; shutil.rmtree("/tmp/x")', "shutil.rmtree"),
        ]
        for code, label in tests:
            with self.subTest(label=label):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_file_write_ask(self):
        tests = [
            ('open("f", "w").write("data")', "write mode"),
            ('open("f", "a").write("data")', "append mode"),
        ]
        for code, label in tests:
            with self.subTest(label=label):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_file_read_allowed(self):
        for code in ['open("f").read()', 'open("f", "r")']:
            with self.subTest(code=code):
                v = check_python_command(code)
                self.assertEqual(v.action, "allow")

    def test_network_operations_ask(self):
        tests = [
            ('import socket; socket.connect(("host", 80))', "socket"),
            ('import requests; requests.get("http://e.com")', "requests"),
        ]
        for code, label in tests:
            with self.subTest(label=label):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_pickle_deserialization_ask(self):
        for code in ['import pickle; pickle.loads(data)', 'import pickle; pickle.load(f)']:
            with self.subTest(code=code):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_ctypes_ask(self):
        v = check_python_command('import ctypes; ctypes.CDLL("lib.so")')
        self.assertEqual(v.action, "ask")

    def test_dynamic_import_ask(self):
        v = check_python_command('__import__("os")')
        self.assertEqual(v.action, "ask")

    def test_subprocess_variants_ask(self):
        tests = [
            'import subprocess; subprocess.call("cmd")',
            'import subprocess; subprocess.check_call("cmd")',
            'import subprocess; subprocess.check_output("cmd")',
            'import subprocess; subprocess.getoutput("ls")',
            'import subprocess; subprocess.getstatusoutput("ls")',
        ]
        for code in tests:
            with self.subTest(code=code[:40]):
                v = check_python_command(code)
                self.assertEqual(v.action, "ask")

    def test_high_threshold_execution_time(self):
        v = check_python_command('import os; os.system("ls")', ask_threshold=90)
        self.assertEqual(v.action, "ask")
        v2 = check_python_command('import os; os.remove("file")', ask_threshold=90)
        self.assertEqual(v2.action, "allow")

    def test_empty_source_allowed(self):
        v = check_python_command("")
        self.assertEqual(v.action, "allow")

    def test_syntax_error_does_not_block(self):
        v = check_python_command("def foo(:")
        self.assertEqual(v.action, "allow")
        self.assertIsInstance(v.score, int)

    def test_verdict_contains_score_and_reason(self):
        v = check_python_command('import os; os.system("ls")')
        self.assertIsInstance(v.score, int)
        self.assertGreater(v.score, 75)
        self.assertIn(v.level, ("safe", "caution", "danger", "critical"))
        self.assertTrue(len(v.reason) > 0)

    def test_safe_modules_not_flagged(self):
        for code in [
            "import math; math.sqrt(16)",
            "from pathlib import Path; Path('f').read_text()",
            "import glob; glob.glob('*.py')",
            "import hashlib; hashlib.md5(b'x')",
        ]:
            with self.subTest(code=code[:30]):
                v = check_python_command(code)
                self.assertEqual(v.action, "allow")


class ShellGuardrailThresholdTest(SimpleTestCase):
    """Edge cases for shell guardrail thresholds."""

    def test_critical_pipeline_blocked(self):
        v = check_shell_command("cat a | bash", ask_threshold=90)
        self.assertEqual(v.action, "ask")

    def test_plain_bash_risky_but_allowed_at_90(self):
        v = check_shell_command("bash a", ask_threshold=90)
        self.assertEqual(v.action, "allow")

    def test_read_commands_safe_at_default_threshold(self):
        for cmd in ["ls", "pwd", "echo hi"]:
            with self.subTest(cmd=cmd):
                v = check_shell_command(cmd)
                self.assertEqual(v.action, "allow")

    def test_everything_ask_at_threshold_zero(self):
        v = check_shell_command("ls", ask_threshold=0)
        self.assertEqual(v.action, "ask")

    def test_score_is_int(self):
        v = check_shell_command("rm -rf /")
        self.assertIsInstance(v.score, int)


class LintShellCommandTest(SimpleTestCase):
    """pureshellcheck lint findings."""

    def test_clean_code_returns_empty(self):
        findings = lint_shell_command("ls -la")
        self.assertIsInstance(findings, list)

    def test_unterminated_string_detected(self):
        findings = lint_shell_command('echo "unterminated')
        self.assertTrue(len(findings) > 0)
        self.assertIn("unterminated", findings[0]["message"].lower())

    def test_finding_structure(self):
        findings = lint_shell_command('echo "unterminated')
        if findings:
            f = findings[0]
            self.assertIn("line", f)
            self.assertIn("severity", f)
            self.assertIn("message", f)
            self.assertIn(f["severity"], ("error", "warning"))

    def test_empty_source(self):
        findings = lint_shell_command("")
        self.assertIsInstance(findings, list)

    def test_variable_quoted_warning(self):
        findings = lint_shell_command("cat $file.txt")
        self.assertTrue(len(findings) > 0)


class _FakeWorkspace:
    def __init__(self, root):
        self.path = str(root)


class _FakeAgent:
    def __init__(self, access=None):
        self._access = access

    def get_agent_setting(self, name):
        if name == "extra_settings" and self._access is not None:
            return {"access": self._access}
        return None


class _FakeSession:
    def __init__(self, root, access=None, agent_access=None):
        self.workspace = _FakeWorkspace(root)
        self.agent = _FakeAgent(agent_access)


class CheckShellPathsTest(SimpleTestCase):
    """Filesystem-target analysis of shell commands (workspace policy)."""

    def setUp(self):
        import tempfile

        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)
        (self.root / "inbox").mkdir()

    def _policy(self, workspace_access=None, agent_access=None):
        from runtime.workspace_access import resolve_policy

        session = _FakeSession(
            self.root, access=workspace_access, agent_access=agent_access
        )
        return resolve_policy(session)

    def test_no_absolute_paths_allowed(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_shell_paths("echo hello world", policy)
        self.assertEqual(v.action, "allow")

    def test_write_redirect_outside_denied(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_shell_paths("echo hi > /tmp/out.txt", policy)
        self.assertEqual(v.action, "deny")

    def test_write_redirect_inside_allowed(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_shell_paths(f"echo hi > {self.root}/inbox/out.txt", policy)
        self.assertEqual(v.action, "allow")

    def test_rm_outside_denied(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_shell_paths("rm -rf /tmp/cache", policy)
        self.assertEqual(v.action, "deny")

    def test_read_outside_denied_by_external_default(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(workspace_access={"read": {"default": "allow"}})
        v = check_shell_paths("cat /etc/passwd", policy)
        self.assertEqual(v.action, "deny")

    def test_read_outside_allowed_via_external_allow(self):
        from runtime.guardrails import check_shell_paths

        policy = self._policy(
            workspace_access={"read": {"default": "allow"}, "write": {"default": "deny"}},
            agent_access={
                "external": {
                    "read": {"default": "deny", "allow": ["/tmp/shared/**"]},
                    "write": {"default": "deny"},
                }
            },
        )
        v = check_shell_paths("cat /tmp/shared/notes.md", policy)
        self.assertEqual(v.action, "allow")

    def test_read_whitelist_cat_classified_read(self):
        """A whitelisted read command classifies its operand as read."""
        from runtime.guardrails import _shell_targets

        self.assertEqual(_shell_targets("cat /etc/passwd"), [("/etc/passwd", "read")])

    def test_unknown_command_failsafe_write(self):
        """Unknown commands are treated as write-capable (fail-safe)."""
        from runtime.guardrails import _shell_targets

        self.assertEqual(_shell_targets("exotic_tool /tmp/thing"), [("/tmp/thing", "write")])

    def test_explicit_writer_is_write(self):
        from runtime.guardrails import _shell_targets

        self.assertEqual(_shell_targets("tar -xf a.tar -C /tmp"), [("/tmp", "write")])

    def test_sed_inplace_flag_makes_write(self):
        from runtime.guardrails import _shell_targets

        self.assertEqual(
            _shell_targets("sed -i s/x/y/ /tmp/f"), [("/tmp/f", "write")]
        )

    def test_sort_output_flag_makes_write(self):
        """sort is read-whitelisted; -o flips it to write."""
        from runtime.guardrails import _shell_targets

        self.assertEqual(
            _shell_targets("sort /tmp/in"), [("/tmp/in", "read")]
        )
        self.assertEqual(
            _shell_targets("sort -o /tmp/out /tmp/in"),
            [("/tmp/out", "write"), ("/tmp/in", "write")],
        )

    def test_perl_inplace_flag_makes_write(self):
        from runtime.guardrails import _shell_targets

        self.assertEqual(
            _shell_targets("perl -i -pe s/x/y/ /tmp/g"), [("/tmp/g", "write")]
        )

    def test_dev_null_write_ignored(self):
        from runtime.guardrails import _shell_targets

        self.assertEqual(_shell_targets("ls /tmp >/dev/null 2>&1"), [("/tmp", "read")])
        self.assertEqual(_shell_targets("echo hi > /dev/null"), [])

    def test_pipeline_resets_command_context(self):
        from runtime.guardrails import _shell_targets

        self.assertEqual(
            _shell_targets("grep foo /tmp/x | tee /tmp/y"),
            [("/tmp/x", "read"), ("/tmp/y", "write")],
        )


class CheckPythonPathsTest(SimpleTestCase):
    """Filesystem-target analysis of Python code (workspace policy)."""

    def setUp(self):
        import tempfile

        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)

    def _policy(self, workspace_access=None, agent_access=None):
        from runtime.workspace_access import resolve_policy

        session = _FakeSession(
            self.root, access=workspace_access, agent_access=agent_access
        )
        return resolve_policy(session)

    def test_plain_code_allowed(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths('print("hello")', policy)
        self.assertEqual(v.action, "allow")

    def test_open_write_outside_denied(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths('open("/tmp/x.txt", "w")', policy)
        self.assertEqual(v.action, "deny")

    def test_open_write_inside_allowed(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths(f'open("{self.root}/in.txt", "w")', policy)
        self.assertEqual(v.action, "allow")

    def test_open_read_inside_allowed(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths(f'open("{self.root}/in.txt", "r")', policy)
        self.assertEqual(v.action, "allow")

    def test_os_remove_outside_denied(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths('import os; os.remove("/tmp/x")', policy)
        self.assertEqual(v.action, "deny")

    def test_dynamic_path_falls_back_to_allow(self):
        from runtime.guardrails import check_python_paths

        policy = self._policy(workspace_access={"write": {"default": "deny"}})
        v = check_python_paths('import os; p = "/tmp/x"; os.remove(p)', policy)
        # non-constant path → not evaluated (falls back to content scoring)
        self.assertEqual(v.action, "allow")
