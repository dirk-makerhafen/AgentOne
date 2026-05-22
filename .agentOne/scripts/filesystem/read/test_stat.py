import importlib.util
import os
import sys
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location('stat_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stat.py'))
_stat_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stat_mod)
stat_tool = _stat_mod.stat


class TestStat(unittest.TestCase):
    """Tests for the stat tool."""

    def test_stat_file(self) -> None:
        """Stat on a file returns exists=True and is_file=True."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('test content')
            f.flush()
            tmp_path = f.name
        try:
            success, result = stat_tool(tmp_path)
            self.assertTrue(success)
            self.assertTrue(result['exists'])
            self.assertTrue(result['is_file'])
            self.assertFalse(result['is_dir'])
            self.assertGreater(result['size'], 0)
        finally:
            os.unlink(tmp_path)

    def test_stat_directory(self) -> None:
        """Stat on a directory returns exists=True and is_dir=True."""
        success, result = stat_tool(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertTrue(result['exists'])
        self.assertTrue(result['is_dir'])
        self.assertFalse(result['is_file'])

    def test_stat_nonexistent(self) -> None:
        """Stat on a non-existent path returns exists=False."""
        success, result = stat_tool('/nonexistent/path/xyz')
        self.assertTrue(success)
        self.assertFalse(result['exists'])
        self.assertFalse(result['is_dir'])
        self.assertFalse(result['is_file'])

    def test_stat_no_path(self) -> None:
        """Stat with an empty path returns an error."""
        success, result = stat_tool('')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])


if __name__ == '__main__':
    unittest.main()
