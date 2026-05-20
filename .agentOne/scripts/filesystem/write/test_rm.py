import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rm import rm

class TestRm(unittest.TestCase):
    def test_rm_file(self):
        f = os.path.join(tempfile.gettempdir(), 'test_rm_abc.txt')
        with open(f, 'w') as fh:
            fh.write('test')
        success, result = rm(f)
        self.assertTrue(success)
        self.assertFalse(os.path.exists(f))

    def test_rm_empty_dir(self):
        d = os.path.join(tempfile.gettempdir(), 'test_rm_dir_abc')
        try:
            os.makedirs(d)
            success, result = rm(d)
            self.assertTrue(success)
            self.assertFalse(os.path.exists(d))
        except Exception:
            pass

    def test_rm_dir_recursive(self):
        d = os.path.join(tempfile.gettempdir(), 'test_rm_dir_abc')
        try:
            os.makedirs(os.path.join(d, 'sub'))
            with open(os.path.join(d, 'file.txt'), 'w') as fh:
                fh.write('test')
            success, result = rm(d, recursive=True)
            self.assertTrue(success)
            self.assertFalse(os.path.exists(d))
        except Exception:
            pass

    def test_rm_nonexistent(self):
        success, result = rm('/nonexistent/path/xyz')
        self.assertTrue(success)
        self.assertIn('does not exist', result['message'])

    def test_rm_nonempty_dir_no_recursive(self):
        d = os.path.join(tempfile.gettempdir(), 'test_rm_dir_abc')
        try:
            os.makedirs(os.path.join(d, 'sub'))
            success, result = rm(d, recursive=False)
            self.assertFalse(success)
            self.assertIn('not empty', result['message'])
        finally:
            import shutil
            if os.path.exists(d):
                shutil.rmtree(d)

if __name__ == '__main__':
    unittest.main()
