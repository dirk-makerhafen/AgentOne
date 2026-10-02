import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from websearch import webSearch


class TestWebSearch(unittest.TestCase):
    """Tests for the webSearch tool."""

    def test_websearch_no_query(self) -> None:
        """webSearch with an empty query returns an error."""
        success, result = webSearch('')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_websearch_basic(self) -> None:
        """webSearch returns a list of results for a valid query."""
        success, result = webSearch('python programming language', num_results=3)
        self.assertTrue(success)
        self.assertEqual(result['query'], 'python programming language')
        self.assertIsInstance(result['results'], list)


if __name__ == '__main__':
    unittest.main()
