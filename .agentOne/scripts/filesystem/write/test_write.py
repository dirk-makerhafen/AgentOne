import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from write import write


class TestWrite(unittest.TestCase):
    """Tests for the write tool."""

    def test_write_file(self) -> None:
        """Write creates a file with the given content."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_write_abc123.txt')
        try:
            success, result = write(tmp_path, 'hello world')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'hello world')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_write_overwrite(self) -> None:
        """Write overwrites an existing file with new content."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_write_abc123.txt')
        try:
            write(tmp_path, 'first')
            success, result = write(tmp_path, 'second')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'second')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_write_creates_dirs(self) -> None:
        """Write creates intermediate directories for nested paths."""
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_dir_xyz', 'nested', 'file.txt')
        try:
            success, result = write(tmp_path, 'nested content')
            self.assertTrue(success)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            parent = os.path.dirname(tmp_path)
            if os.path.exists(parent):
                os.rmdir(parent)
            grandparent = os.path.dirname(parent)
            if os.path.exists(grandparent):
                os.rmdir(grandparent)

    def test_write_no_path(self) -> None:
        """Write with an empty path returns an error."""
        success, result = write('', 'content')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])


if __name__ == '__main__':
    unittest.main()
