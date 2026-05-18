import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from websearch import webSearch

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestWebSearch(unittest.TestCase):
    def test_websearch_no_query(self):
        success, result = webSearch(MockCaller(), '')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_websearch_basic(self):
        success, result = webSearch(MockCaller(), 'python programming language', num_results=3)
        self.assertTrue(success)
        self.assertEqual(result['query'], 'python programming language')
        self.assertIsInstance(result['results'], list)

if __name__ == '__main__':
    unittest.main()
