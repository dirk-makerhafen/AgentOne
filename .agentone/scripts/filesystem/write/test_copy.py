import importlib.util
import os
import sys
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location('copy_tool', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'copy.py'))
_copy_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_copy_mod)
copy_tool = _copy_mod.copy


class TestCopy(unittest.TestCase):
    """Tests for the copy tool."""

    def test_copy_file(self) -> None:
        """Copy a file creates an identical destination file."""
        src = os.path.join(tempfile.gettempdir(), 'test_copy_src.txt')
        dst = os.path.join(tempfile.gettempdir(), 'test_copy_dst.txt')
        try:
            with open(src, 'w') as f:
                f.write('test content')
            success, result = copy_tool(src, dst)
            self.assertTrue(success)
            with open(dst, 'r') as f:
                self.assertEqual(f.read(), 'test content')
        finally:
            for p in [src, dst]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_copy_dir_recursive(self) -> None:
        """Copy a directory recursively copies all contents."""
        src_dir = os.path.join(tempfile.gettempdir(), 'test_copy_src_dir')
        dst_dir = os.path.join(tempfile.gettempdir(), 'test_copy_dst_dir')
        try:
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, 'file.txt'), 'w') as f:
                f.write('test')
            success, result = copy_tool(src_dir, dst_dir, recursive=True)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(os.path.join(dst_dir, 'file.txt')))
        finally:
            import shutil
            for p in [src_dir, dst_dir]:
                if os.path.exists(p):
                    shutil.rmtree(p)

    def test_copy_dir_no_recursive(self) -> None:
        """Copy a directory without recursive flag returns an error."""
        src_dir = os.path.join(tempfile.gettempdir(), 'test_copy_src_dir')
        try:
            os.makedirs(src_dir, exist_ok=True)
            success, result = copy_tool(src_dir, os.path.join(tempfile.gettempdir(), 'dst'))
            self.assertFalse(success)
            self.assertIn('recursive=True', result['message'])
        finally:
            if os.path.exists(src_dir):
                os.rmdir(src_dir)

    def test_copy_source_not_found(self) -> None:
        """Copy a non-existent source returns an error."""
        success, result = copy_tool('/nonexistent/xyz', '/tmp/dst')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])


if __name__ == '__main__':
    unittest.main()
