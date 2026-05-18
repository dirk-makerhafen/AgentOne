import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from diff import diff

class MockCaller:
    def __init__(self):
        self.workingdir = tempfile.gettempdir()

class TestDiff(unittest.TestCase):
    def test_file_diff(self):
        f1 = os.path.join(tempfile.gettempdir(), 'test_diff_1.txt')
        f2 = os.path.join(tempfile.gettempdir(), 'test_diff_2.txt')
        try:
            with open(f1, 'w') as fh:
                fh.write('line1\nline2\nline3\n')
            with open(f2, 'w') as fh:
                fh.write('line1\nmodified\nline3\n')
            success, result = diff(MockCaller(), path=f1, target=f2)
            self.assertTrue(success)
            self.assertTrue(result['has_changes'])
            self.assertIn('modified', result['diff'])
        finally:
            for p in [f1, f2]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_file_diff_no_changes(self):
        f1 = os.path.join(tempfile.gettempdir(), 'test_diff_1.txt')
        f2 = os.path.join(tempfile.gettempdir(), 'test_diff_2.txt')
        try:
            with open(f1, 'w') as fh:
                fh.write('same content\n')
            with open(f2, 'w') as fh:
                fh.write('same content\n')
            success, result = diff(MockCaller(), path=f1, target=f2)
            self.assertTrue(success)
            self.assertFalse(result['has_changes'])
        finally:
            for p in [f1, f2]:
                if os.path.exists(p):
                    os.unlink(p)

if __name__ == '__main__':
    unittest.main()
