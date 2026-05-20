import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grep import grep

class TestGrep(unittest.TestCase):
    def test_grep_in_dir(self):
        success, result = grep('def ', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)
        self.assertGreater(result['file_count'], 0)

    def test_grep_no_pattern(self):
        success, result = grep('')
        self.assertFalse(success)
        self.assertIn('Pattern not provided', result['message'])

    def test_grep_with_include(self):
        success, result = grep('def ', path=os.path.dirname(os.path.abspath(__file__)), include='*.py')
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)

    def test_grep_regex(self):
        success, result = grep(r'def test_\w+', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)

    def test_grep_nonexistent_dir(self):
        success, result = grep('pattern', path='/nonexistent/dir/xyz')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])

if __name__ == '__main__':
    unittest.main()
