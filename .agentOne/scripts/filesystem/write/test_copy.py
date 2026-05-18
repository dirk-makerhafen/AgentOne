import sys
import os
import tempfile
import unittest
import importlib.util

_spec = importlib.util.spec_from_file_location('copy_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'copy.py'))
_copy_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_copy_mod)
copy_tool = _copy_mod.copy

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestCopy(unittest.TestCase):
    def test_copy_file(self):
        src = os.path.join(tempfile.gettempdir(), 'test_copy_src.txt')
        dst = os.path.join(tempfile.gettempdir(), 'test_copy_dst.txt')
        try:
            with open(src, 'w') as f:
                f.write('test content')
            success, result = copy_tool(MockCaller(), src, dst)
            self.assertTrue(success)
            with open(dst, 'r') as f:
                self.assertEqual(f.read(), 'test content')
        finally:
            for p in [src, dst]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_copy_dir_recursive(self):
        src_dir = os.path.join(tempfile.gettempdir(), 'test_copy_src_dir')
        dst_dir = os.path.join(tempfile.gettempdir(), 'test_copy_dst_dir')
        try:
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, 'file.txt'), 'w') as f:
                f.write('test')
            success, result = copy_tool(MockCaller(), src_dir, dst_dir, recursive=True)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(os.path.join(dst_dir, 'file.txt')))
        finally:
            import shutil
            for p in [src_dir, dst_dir]:
                if os.path.exists(p):
                    shutil.rmtree(p)

    def test_copy_dir_no_recursive(self):
        src_dir = os.path.join(tempfile.gettempdir(), 'test_copy_src_dir')
        try:
            os.makedirs(src_dir, exist_ok=True)
            success, result = copy_tool(MockCaller(), src_dir, os.path.join(tempfile.gettempdir(), 'dst'))
            self.assertFalse(success)
            self.assertIn('recursive=true', result['message'])
        finally:
            if os.path.exists(src_dir):
                os.rmdir(src_dir)

    def test_copy_source_not_found(self):
        success, result = copy_tool(MockCaller(), '/nonexistent/xyz', '/tmp/dst')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])

if __name__ == '__main__':
    unittest.main()
