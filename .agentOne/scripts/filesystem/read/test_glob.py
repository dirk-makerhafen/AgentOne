import sys
import os
import tempfile
import unittest
import importlib.util

_spec = importlib.util.spec_from_file_location('glob_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glob.py'))
_glob_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_glob_mod)
glob_tool = _glob_mod.glob

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestGlob(unittest.TestCase):
    def test_glob_py_files(self):
        success, result = glob_tool(MockCaller(), '**/*.py', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['count'], 0)
        self.assertIsInstance(result['matches'], list)

    def test_glob_no_pattern(self):
        success, result = glob_tool(MockCaller(), '')
        self.assertFalse(success)
        self.assertIn('Pattern not provided', result['message'])

    def test_glob_nonexistent_dir(self):
        success, result = glob_tool(MockCaller(), '*.txt', path='/nonexistent/dir/xyz')
        self.assertTrue(success)
        self.assertEqual(result['count'], 0)

    def test_glob_specific_extension(self):
        success, result = glob_tool(MockCaller(), '*.py', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        for match in result['matches']:
            self.assertTrue(match.endswith('.py'))

if __name__ == '__main__':
    unittest.main()
