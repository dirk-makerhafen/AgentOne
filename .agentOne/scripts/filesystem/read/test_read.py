import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from read import read


class TestRead(unittest.TestCase):
    """Tests for the read tool."""

    def test_read_file(self) -> None:
        """Read a file returns its content with line numbers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('line1\nline2\nline3\n')
            f.flush()
            tmp_path = f.name
        try:
            success, result = read(tmp_path)
            self.assertTrue(success)
            self.assertEqual(result['type'], 'file')
            self.assertIn('1: line1', result['content'])
            self.assertIn('2: line2', result['content'])
        finally:
            os.unlink(tmp_path)

    def test_read_directory(self) -> None:
        """Read a directory returns its listing."""
        success, result = read(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertEqual(result['type'], 'directory')
        self.assertIsInstance(result['content'], list)
        self.assertTrue(len(result['content']) > 0)

    def test_read_nonexistent(self) -> None:
        """Read a non-existent path returns an error."""
        success, result = read('/nonexistent/path/xyz')
        self.assertFalse(success)
        self.assertIn('does not exist', result['message'])

    def test_read_offset_limit(self) -> None:
        """Read with offset and limit returns only the requested lines."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(10):
                f.write(f'line{i}\n')
            f.flush()
            tmp_path = f.name
        try:
            success, result = read(tmp_path, offset=3, limit=2)
            self.assertTrue(success)
            self.assertIn('3: line2', result['content'])
            self.assertIn('4: line3', result['content'])
            self.assertNotIn('5: line4', result['content'])
        finally:
            os.unlink(tmp_path)

    def test_read_no_path(self) -> None:
        """Read with an empty path returns an error."""
        success, result = read('')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])


if __name__ == '__main__':
    unittest.main()
