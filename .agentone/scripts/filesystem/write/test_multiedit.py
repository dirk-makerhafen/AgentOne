import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from multiedit import multiedit


class TestMultiedit(unittest.TestCase):
    """Tests for the multiedit tool."""

    def test_multiedit_basic(self) -> None:
        """Multiedit applies multiple edits to a file sequentially."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_multiedit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\nfoo bar\n')
            edits = [
                {'old_string': 'hello', 'new_string': 'goodbye'},
                {'old_string': 'foo', 'new_string': 'baz'},
            ]
            success, result = multiedit(tmp_path, edits)
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'goodbye world\nbaz bar\n')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_multiedit_partial_failure(self) -> None:
        """Multiedit applies edits until one fails and reports partial success."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_multiedit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\n')
            edits = [
                {'old_string': 'hello', 'new_string': 'goodbye'},
                {'old_string': 'nonexistent', 'new_string': 'xyz'},
            ]
            success, result = multiedit(tmp_path, edits)
            self.assertFalse(success)
            self.assertEqual(result['edits_applied'], 1)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_multiedit_no_edits(self) -> None:
        """Multiedit with an empty edits list returns an error."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_multiedit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello\n')
            success, result = multiedit(tmp_path, [])
            self.assertFalse(success)
            self.assertIn('No edits', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_multiedit_file_not_found(self) -> None:
        """Multiedit on a non-existent file returns an error."""
        success, result = multiedit('/nonexistent/path/xyz', [{'old_string': 'a', 'new_string': 'b'}])
        self.assertFalse(success)
        self.assertIn('not found', result['message'])


if __name__ == '__main__':
    unittest.main()
