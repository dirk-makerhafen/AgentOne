import importlib.util
import os
import sys
import unittest

_spec = importlib.util.spec_from_file_location('glob_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glob.py'))
_glob_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_glob_mod)
glob_tool = _glob_mod.glob


class TestGlob(unittest.TestCase):
    """Tests for the glob tool."""

    def test_glob_py_files(self) -> None:
        """Glob for Python files returns matches with a positive count."""
        success, result = glob_tool('**/*.py', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['count'], 0)
        self.assertIsInstance(result['matches'], list)

    def test_glob_no_pattern(self) -> None:
        """Glob with an empty pattern returns an error."""
        success, result = glob_tool('')
        self.assertFalse(success)
        self.assertIn('Pattern not provided', result['message'])

    def test_glob_nonexistent_dir(self) -> None:
        """Glob in a non-existent directory returns zero matches."""
        success, result = glob_tool('*.txt', path='/nonexistent/dir/xyz')
        self.assertTrue(success)
        self.assertEqual(result['count'], 0)

    def test_glob_specific_extension(self) -> None:
        """Glob with a specific extension only returns files with that extension."""
        success, result = glob_tool('*.py', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        for match in result['matches']:
            self.assertTrue(match.endswith('.py'))


if __name__ == '__main__':
    unittest.main()
