import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mkdir import mkdir

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestMkdir(unittest.TestCase):
    def test_mkdir_basic(self):
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_abc')
        try:
            success, result = mkdir(MockCaller(), d)
            self.assertTrue(success)
            self.assertTrue(os.path.isdir(d))
        finally:
            if os.path.isdir(d):
                os.rmdir(d)

    def test_mkdir_parents(self):
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_a', 'test_mkdir_b', 'test_mkdir_c')
        try:
            success, result = mkdir(MockCaller(), d, parents=True)
            self.assertTrue(success)
            self.assertTrue(os.path.isdir(d))
        finally:
            import shutil
            if os.path.isdir(os.path.join(tempfile.gettempdir(), 'test_mkdir_a')):
                shutil.rmtree(os.path.join(tempfile.gettempdir(), 'test_mkdir_a'))

    def test_mkdir_exists_ok(self):
        d = os.path.join(tempfile.gettempdir(), 'test_mkdir_abc')
        try:
            os.makedirs(d)
            success, result = mkdir(MockCaller(), d, exist_ok=True)
            self.assertTrue(success)
        finally:
            if os.path.isdir(d):
                os.rmdir(d)

    def test_mkdir_no_path(self):
        success, result = mkdir(MockCaller(), '')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])

if __name__ == '__main__':
    unittest.main()
