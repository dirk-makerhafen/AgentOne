import sys
import os
import tempfile
import unittest
import importlib.util

_spec = importlib.util.spec_from_file_location('stat_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stat.py'))
_stat_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stat_mod)
stat_tool = _stat_mod.stat

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestStat(unittest.TestCase):
    def test_stat_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('test content')
            f.flush()
            tmp_path = f.name
        try:
            success, result = stat_tool(MockCaller(), tmp_path)
            self.assertTrue(success)
            self.assertTrue(result['exists'])
            self.assertTrue(result['is_file'])
            self.assertFalse(result['is_dir'])
            self.assertGreater(result['size'], 0)
        finally:
            os.unlink(tmp_path)

    def test_stat_directory(self):
        success, result = stat_tool(MockCaller(), os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertTrue(result['exists'])
        self.assertTrue(result['is_dir'])
        self.assertFalse(result['is_file'])

    def test_stat_nonexistent(self):
        success, result = stat_tool(MockCaller(), '/nonexistent/path/xyz')
        self.assertTrue(success)
        self.assertFalse(result['exists'])
        self.assertFalse(result['is_dir'])
        self.assertFalse(result['is_file'])

    def test_stat_no_path(self):
        success, result = stat_tool(MockCaller(), '')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])

if __name__ == '__main__':
    unittest.main()
