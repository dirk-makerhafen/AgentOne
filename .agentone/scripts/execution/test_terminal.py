import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from terminal import terminal_exec, terminal_kill, terminal_list, terminal_poll, terminal_send


def _session():
    session = MagicMock()
    session.model.pk = 123
    return session


class TestTerminalTools(unittest.TestCase):
    """Tests for the persistent terminal tools (manager is mocked)."""

    def test_exec_delegates_to_manager(self) -> None:
        """terminal_exec forwards command/terminal/timeout and maps success."""
        with patch("runtime.terminal.manager.exec_command") as exec_cmd:
            exec_cmd.return_value = {
                'status': 'success', 'stdout': 'hi\n', 'stderr': '',
                'return_code': 0, 'terminal': 'dev',
            }
            success, result = terminal_exec(_session(), command="echo hi", terminal="dev", timeout=30)
            self.assertTrue(success)
            self.assertEqual(result['stdout'], 'hi\n')
            exec_cmd.assert_called_once()
            _, kwargs = exec_cmd.call_args
            self.assertEqual(kwargs.get("name"), "dev")
            self.assertEqual(kwargs.get("timeout"), 30)

    def test_exec_failure_maps_to_false(self) -> None:
        """Non-zero return codes map to success=False."""
        with patch("runtime.terminal.manager.exec_command") as exec_cmd:
            exec_cmd.return_value = {
                'status': 'error', 'stdout': '', 'stderr': 'boom',
                'return_code': 1, 'terminal': 'default',
            }
            success, result = terminal_exec(_session(), command="exit 1")
            self.assertFalse(success)
            self.assertEqual(result['return_code'], 1)

    def test_exec_manager_error_returns_error_tuple(self) -> None:
        """Missing tmux/libtmux surfaces as (False, error) instead of raising."""
        with patch("runtime.terminal.manager.exec_command", side_effect=RuntimeError("tmux binary not found")):
            success, result = terminal_exec(_session(), command="echo hi")
            self.assertFalse(success)
            self.assertIn('tmux', result['stderr'])

    def test_send_and_poll(self) -> None:
        """terminal_send submits keystrokes; terminal_poll reads output."""
        with patch("runtime.terminal.manager.send_input") as send:
            send.return_value = {'status': 'success', 'terminal': 'default', 'submitted': True}
            success, result = terminal_send(_session(), text="y", terminal="default")
            self.assertTrue(success)
            self.assertTrue(result['submitted'])
        with patch("runtime.terminal.manager.poll_output") as poll:
            poll.return_value = {'status': 'success', 'terminal': 'default', 'output': 'hello'}
            success, result = terminal_poll(_session(), terminal="default", lines=50)
            self.assertTrue(success)
            self.assertEqual(result['output'], 'hello')

    def test_list_and_kill(self) -> None:
        """terminal_list returns rows; terminal_kill maps status."""
        with patch("runtime.terminal.manager.list_terminals") as lst:
            lst.return_value = [{'name': 'dev', 'status': 'running', 'alive': True}]
            success, result = terminal_list(_session())
            self.assertTrue(success)
            self.assertEqual(result['terminals'][0]['name'], 'dev')
        with patch("runtime.terminal.manager.kill_terminal") as kill:
            kill.return_value = {'status': 'success', 'terminal': 'dev'}
            success, _ = terminal_kill(_session(), terminal="dev")
            self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
