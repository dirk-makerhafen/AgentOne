import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shell import shell


class TestShell(unittest.TestCase):
    """Tests for the shell tool."""

    def test_shell_echo(self) -> None:
        """Run echo and verify stdout contains the expected string."""
        success, result = shell(source="echo hello")
        self.assertTrue(success)
        self.assertEqual(result['stdout'].strip(), 'hello')
        self.assertEqual(result['return_code'], 0)

    def test_shell_pwd(self) -> None:
        """Run pwd and verify the command succeeds."""
        success, result = shell(source="pwd")
        self.assertTrue(success)
        self.assertIn(result['return_code'], [0])

    def test_shell_error(self) -> None:
        """Run a command that exits with a non-zero code."""
        success, result = shell(source="exit 42")
        self.assertFalse(success)
        self.assertEqual(result['return_code'], 42)

    def test_shell_env(self) -> None:
        """Run echo on an environment variable and verify non-empty output."""
        success, result = shell(source="echo $HOME")
        self.assertTrue(success)
        self.assertTrue(len(result['stdout'].strip()) > 0)


if __name__ == '__main__':
    unittest.main()
