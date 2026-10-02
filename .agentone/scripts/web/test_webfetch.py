import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webfetch import webFetch


class TestWebFetch(unittest.TestCase):
    """Tests for the webFetch tool."""

    def test_webfetch_no_url(self) -> None:
        """webFetch with an empty URL returns an error."""
        success, result = webFetch('')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_webfetch_basic(self) -> None:
        """webFetch fetches a URL and returns content."""
        success, result = webFetch('https://httpbin.org/html', format='text')
        self.assertTrue(success)
        self.assertIn('url', result)
        self.assertIn('content', result)


if __name__ == '__main__':
    unittest.main()
