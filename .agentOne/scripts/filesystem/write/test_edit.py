import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edit import edit

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestEdit(unittest.TestCase):
    def test_edit_single(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\n')
            success, result = edit(MockCaller(), tmp_path, 'hello', 'goodbye')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'goodbye world\n')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_replace_all(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('foo bar foo\n')
            success, result = edit(MockCaller(), tmp_path, 'foo', 'baz', replace_all=True)
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'baz bar baz\n')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_not_found(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello world\n')
            success, result = edit(MockCaller(), tmp_path, 'xyz', 'abc')
            self.assertFalse(success)
            self.assertIn('not found', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_identical(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello\n')
            success, result = edit(MockCaller(), tmp_path, 'hello', 'hello')
            self.assertFalse(success)
            self.assertIn('identical', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_edit_multiple_no_replace_all(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_edit_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('foo bar foo\n')
            success, result = edit(MockCaller(), tmp_path, 'foo', 'baz', replace_all=False)
            self.assertFalse(success)
            self.assertIn('Found 2 occurrences', result['message'])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

if __name__ == '__main__':
    unittest.main()
