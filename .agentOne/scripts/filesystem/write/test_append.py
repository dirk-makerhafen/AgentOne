import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from append import append

class TestAppend(unittest.TestCase):
    def test_append_to_file(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_append_abc.txt')
        try:
            with open(tmp_path, 'w') as f:
                f.write('hello ')
            success, result = append(tmp_path, 'world')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'hello world')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_append_creates_file(self):
        tmp_path = os.path.join(tempfile.gettempdir(), 'test_append_abc.txt')
        try:
            success, result = append(tmp_path, 'new content')
            self.assertTrue(success)
            with open(tmp_path, 'r') as f:
                self.assertEqual(f.read(), 'new content')
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_append_no_path(self):
        success, result = append('', 'content')
        self.assertFalse(success)
        self.assertIn('Path not provided', result['message'])

if __name__ == '__main__':
    unittest.main()
