import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kill import kill


class TestKill(unittest.TestCase):
    """Tests for the kill tool."""

    def test_kill_missing_pid(self) -> None:
        """Kill with a non-existent PID returns an error."""
        success, result = kill(pid=999999)
        self.assertFalse(success)
        self.assertEqual(result['status'], 'error')
        self.assertIn('not found', result['message'])

    def test_kill_no_args(self) -> None:
        """Kill with neither pid nor name returns an error."""
        success, result = kill()
        self.assertFalse(success)
        self.assertIn('Either pid or name', result['message'])

    def test_kill_invalid_signal(self) -> None:
        """Kill with an invalid signal name returns an error."""
        success, result = kill(name='nonexistent_proc_xyz', signal_name='INVALID')
        self.assertFalse(success)
        self.assertIn('No matching processes found', result['message'])


if __name__ == '__main__':
    unittest.main()
