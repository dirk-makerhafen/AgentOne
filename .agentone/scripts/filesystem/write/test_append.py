import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from append import append


class TestAppend(unittest.TestCase):
    """Tests for the append tool."""

    def test_append_to_file(self) -> None:
        """Append content to an existing file adds to the end."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_append_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello ')
            success, result = append(tmp_path, 'world')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'hello world')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_append_creates_file(self) -> None:
        """Append to a non-existent file creates it with the content."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_append_abc.txt')
        try:
            success, result = append(tmp_path, 'new content')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'new content')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_append_no_path(self) -> None:
        """Append with an empty path returns an error."""
        success, result = append('', 'content')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])


if __name__ == '__main__':
    unittest.main()
