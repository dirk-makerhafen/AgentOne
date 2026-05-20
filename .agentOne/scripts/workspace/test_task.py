import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from task import task

class TestTask(unittest.TestCase):
    def test_task_basic(self):
        success, result = task( description='test task', prompt='Do something')
        self.assertTrue(success)
        self.assertIn('task_id', result)
        self.assertEqual(result['description'], 'test task')

    def test_task_no_prompt(self):
        success, result = task( description='test', prompt='')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_task_auto_description(self):
        success, result = task( description='', prompt='This is a very long prompt that should be truncated')
        self.assertTrue(success)
        self.assertLessEqual(len(result['description']), 50)

if __name__ == '__main__':
    unittest.main()
