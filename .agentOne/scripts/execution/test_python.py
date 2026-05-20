import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python import python

class TestPython(unittest.TestCase):
    def test_python_hello(self):
        success, result = python(source="print('hello')")
        self.assertTrue(success)
        self.assertEqual(result['stdout'].strip(), 'hello')
        self.assertEqual(result['return_code'], 0)

    def test_python_math(self):
        success, result = python(source="print(2 + 3)")
        self.assertTrue(success)
        self.assertEqual(result['stdout'].strip(), '5')

    def test_python_error(self):
        success, result = python(source="raise ValueError('test error')")
        self.assertFalse(success)
        self.assertIn('ValueError', result['stderr'])
        self.assertNotEqual(result['return_code'], 0)

    def test_python_empty(self):
        success, result = python(source="")
        self.assertTrue(success)
        self.assertEqual(result['return_code'], 0)

if __name__ == '__main__':
    unittest.main()
