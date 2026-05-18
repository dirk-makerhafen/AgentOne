import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webfetch import webFetch

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestWebFetch(unittest.TestCase):
    def test_webfetch_no_url(self):
        success, result = webFetch(MockCaller(), '')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_webfetch_basic(self):
        success, result = webFetch(MockCaller(), 'https://httpbin.org/html', format='text')
        self.assertTrue(success)
        self.assertIn('url', result)
        self.assertIn('content', result)

if __name__ == '__main__':
    unittest.main()
