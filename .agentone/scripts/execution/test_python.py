import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python import python


class TestPython(unittest.TestCase):
    """Tests for the python tool."""

    def test_python_hello(self) -> None:
        """Execute a simple print statement and check stdout."""
        success, result = python(source="print('hello')")
        self.assertTrue(success)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['stdout'].strip(), 'hello')
        self.assertEqual(result['return_code'], 0)

    def test_python_math(self) -> None:
        """Execute a math expression and check the output."""
        success, result = python(source="print(2 + 3)")
        self.assertTrue(success)
        self.assertEqual(result['stdout'].strip(), '5')

    def test_python_error(self) -> None:
        """Execute code that raises an exception and check stderr."""
        success, result = python(source="raise ValueError('test error')")
        self.assertFalse(success)
        self.assertEqual(result['status'], 'error')
        self.assertIn('ValueError', result['stderr'])
        self.assertNotEqual(result['return_code'], 0)

    def test_python_returns_text_only(self) -> None:
        """Script output is text: no parsed-data key, stdout untouched."""
        success, result = python(
            source="import json; print(json.dumps(['a', 'b']))")
        self.assertTrue(success)
        self.assertNotIn('data', result)
        self.assertEqual(result['stdout'].strip(), '["a", "b"]')
        self.assertEqual(
            set(result.keys()),
            {'status', 'stdout', 'stderr', 'return_code'},
        )

    def test_python_empty(self) -> None:
        """Execute an empty source string and verify success."""
        success, result = python(source="")
        self.assertTrue(success)
        self.assertEqual(result['return_code'], 0)


if __name__ == '__main__':
    unittest.main()
