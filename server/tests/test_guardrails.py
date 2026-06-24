"""Tests for the guardrail system (runtime/guardrails.py).

Uses SimpleTestCase (no DB) since all functions are pure.
"""
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
