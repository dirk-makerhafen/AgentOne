import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grep import grep


class TestGrep(unittest.TestCase):
    """Tests for the grep tool."""

    def test_grep_in_dir(self) -> None:
        """Grep a directory for a common pattern returns matches."""
        success, result = grep('def ', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)
        self.assertGreater(result['file_count'], 0)

    def test_grep_no_pattern(self) -> None:
        """Grep with an empty pattern returns an error."""
        success, result = grep('')
        self.assertFalse(success)
        self.assertIn('Pattern not provided', result['message'])

    def test_grep_with_include(self) -> None:
        """Grep with an include filter restricts matches to matching files."""
        success, result = grep('def ', path=os.path.dirname(os.path.abspath(__file__)), include='*.py')
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)

    def test_grep_regex(self) -> None:
        """Grep with a regex pattern finds matching lines."""
        success, result = grep(r'def test_\w+', path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)

    def test_grep_nonexistent_dir(self) -> None:
        """Grep a non-existent directory returns an error."""
        success, result = grep('pattern', path='/nonexistent/dir/xyz')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])

    def test_grep_file_path_searches_that_file(self) -> None:
        """Grep with a file path searches the file (not silent empty)."""
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'grep.py')
        success, result = grep(r'def grep\(', path=target)
        self.assertTrue(success)
        self.assertGreater(result['match_count'], 0)
        self.assertEqual(result['file_count'], 1)

    def test_grep_file_path_no_match(self) -> None:
        """Grep with a file path and no hit returns empty success."""
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'grep.py')
        success, result = grep('zzz_no_such_token_zzz', path=target)
        self.assertTrue(success)
        self.assertEqual(result['match_count'], 0)


if __name__ == '__main__':
    unittest.main()
