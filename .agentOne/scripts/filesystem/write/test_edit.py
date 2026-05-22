import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edit import edit


class TestEdit(unittest.TestCase):
    """Tests for the edit tool."""

    def test_edit_single(self) -> None:
        """Edit replaces the first occurrence of a string in a file."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\n')
            success, result = edit(tmp_path, 'hello', 'goodbye')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'goodbye world\n')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_replace_all(self) -> None:
        """Edit with replace_all=True replaces all occurrences."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('foo bar foo\n')
            success, result = edit(tmp_path, 'foo', 'baz', replace_all=True)
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'baz bar baz\n')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_not_found(self) -> None:
        """Edit with a non-existent old_string returns an error."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\n')
            success, result = edit(tmp_path, 'xyz', 'abc')
            self.assertFalse(success)
            self.assertIn('not found', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_identical(self) -> None:
        """Edit with identical old and new strings returns an error."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello\n')
            success, result = edit(tmp_path, 'hello', 'hello')
            self.assertFalse(success)
            self.assertIn('identical', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_multiple_no_replace_all(self) -> None:
        """Edit with multiple matches and replace_all=False returns an error."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('foo bar foo\n')
            success, result = edit(tmp_path, 'foo', 'baz', replace_all=False)
            self.assertFalse(success)
            self.assertIn('Found 2 occurrences', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main()
