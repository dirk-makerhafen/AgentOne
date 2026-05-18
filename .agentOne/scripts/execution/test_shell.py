import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shell import shell

class MockCaller:
    def __init__(self):
        self.workingdir = os.getcwd()

class TestShell(unittest.TestCase):
    def test_shell_echo(self):
        success, result = shell(MockCaller(), source="echo hello")
        self.assertTrue(success)
        self.assertEqual(result['stdout'].strip(), 'hello')
        self.assertEqual(result['return_code'], 0)

    def test_shell_pwd(self):
        success, result = shell(MockCaller(), source="pwd")
        self.assertTrue(success)
        self.assertIn(result['return_code'], [0])

    def test_shell_error(self):
        success, result = shell(MockCaller(), source="exit 42")
        self.assertFalse(success)
        self.assertEqual(result['return_code'], 42)

    def test_shell_env(self):
        success, result = shell(MockCaller(), source="echo $HOME")
        self.assertTrue(success)
        self.assertTrue(len(result['stdout'].strip()) > 0)

if __name__ == '__main__':
    unittest.main()
