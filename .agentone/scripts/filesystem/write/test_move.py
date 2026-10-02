import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from move import move


class TestMove(unittest.TestCase):
    """Tests for the move tool."""

    def test_move_file(self) -> None:
        """Move a file removes the source and creates the destination."""
        src = os.path.join(tempfile.gettempdir(), 'test_move_src.txt')
        dst = os.path.join(tempfile.gettempdir(), 'test_move_dst.txt')
        try:
            with open(src, 'w') as f:
                f.write('test content')
            success, result = move(src, dst)
            self.assertTrue(success)
            self.assertFalse(os.path.exists(src))
            self.assertTrue(os.path.exists(dst))
            with open(dst, 'r') as f:
                self.assertEqual(f.read(), 'test content')
        finally:
            for p in [src, dst]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_move_source_not_found(self) -> None:
        """Move a non-existent source returns an error."""
        success, result = move('/nonexistent/xyz', '/tmp/dst')
        self.assertFalse(success)
        self.assertIn('not found', result['message'])


if __name__ == '__main__':
    unittest.main()
