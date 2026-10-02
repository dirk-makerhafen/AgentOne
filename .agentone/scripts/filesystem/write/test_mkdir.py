import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mkdir import mkdir


class TestMkdir(unittest.TestCase):
    """Tests for the mkdir tool."""

    def test_mkdir_basic(self) -> None:
        """Mkdir creates a single directory."""
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_abc')
        try:
            success, result = mkdir(d)
            self.assertTrue(success)
            self.assertTrue(os.path.isdir(d))
        finally:
            if os.path.isdir(d):
                os.rmdir(d)

    def test_mkdir_parents(self) -> None:
        """Mkdir with parents=True creates intermediate directories."""
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_a', 'test_mkdir_b', 'test_mkdir_c')
        try:
            success, result = mkdir(d, parents=True)
            self.assertTrue(success)
            self.assertTrue(os.path.isdir(d))
        finally:
            import shutil
            if os.path.isdir(os.path.join(tempfile.gettempdir(), 'test_mkdir_a')):
                shutil.rmtree(os.path.join(tempfile.gettempdir(), 'test_mkdir_a'))

    def test_mkdir_exists_ok(self) -> None:
        """Mkdir with exist_ok=True does not error on existing directory."""
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_abc')
        try:
            os.makedirs(d)
            success, result = mkdir(d, exist_ok=True)
            self.assertTrue(success)
        finally:
            if os.path.isdir(d):
                os.rmdir(d)

    def test_mkdir_no_path(self) -> None:
        """Mkdir with an empty path returns an error."""
        success, result = mkdir('')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])


if __name__ == '__main__':
    unittest.main()
