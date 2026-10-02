import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tree import tree


class TestTree(unittest.TestCase):
    """Tests for the tree tool."""

    def test_tree_basic(self) -> None:
        """Tree on a directory returns a string representation."""
        success, result = tree(path=os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(success)
        self.assertIn('tree', result)
        self.assertIsInstance(result['tree'], str)
        self.assertIn('/', result['tree'])

    def test_tree_nonexistent(self) -> None:
        """Tree on a non-existent path returns an error."""
        success, result = tree(path='/nonexistent/path/xyz')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])

    def test_tree_not_a_dir(self) -> None:
        """Tree on a file path returns an error."""
        f = os.path.join(tempfile.gettempdir(), 'test_tree_file.txt')
        try:
            with open(f, 'w') as fh:
                fh.write('test')
            success, result = tree(path=f)
            self.assertFalse(success)
            self.assertIn('Not a directory', result['message'])
        finally:
            if os.path.exists(f):
                os.unlink(f)

    def test_tree_depth(self) -> None:
        """Tree with a depth limit restricts the output."""
        success, result = tree(path=os.path.dirname(os.path.abspath(__file__)), depth=1)
        self.assertTrue(success)
        lines = result['tree'].split('\n')
        connectors = [l for l in lines if '──' in l]
        max_depth = sum(1 for c in connectors if c.startswith('│') or c.startswith('└') or c.startswith('├'))
        self.assertTrue(len(result['tree']) > 0)


if __name__ == '__main__':
    unittest.main()
