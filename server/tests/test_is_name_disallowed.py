from runtime.agents.agent import is_name_disallowed
from django.test import SimpleTestCase


class IsNameDisallowedTest(SimpleTestCase):
    """Pure-function tests for ``is_name_disallowed`` wildcard matching.

    Uses ``SimpleTestCase`` (no DB) since there are no model dependencies.
    """

    def test_exact_match(self):
        self.assertTrue(is_name_disallowed("tree", "fs", ["tree"]))

    def test_exact_name_diff_group(self):
        self.assertFalse(is_name_disallowed("tree", "fs", ["other.tree"]))

    def test_prefix_wildcard(self):
        self.assertTrue(is_name_disallowed("foobar", "fs", ["foo*"]))

    def test_suffix_wildcard(self):
        self.assertTrue(is_name_disallowed("foobar", "fs", ["*bar"]))

    def test_group_star(self):
        self.assertTrue(is_name_disallowed("anything", "fs", ["fs.*"]))

    def test_group_prefix(self):
        self.assertTrue(is_name_disallowed("foobar", "fs", ["fs.foo*"]))
        self.assertFalse(is_name_disallowed("bazbar", "fs", ["fs.foo*"]))

    def test_group_suffix(self):
        self.assertTrue(is_name_disallowed("foobar", "fs", ["fs.*bar"]))
        self.assertFalse(is_name_disallowed("foobaz", "fs", ["fs.*bar"]))

    def test_no_match(self):
        self.assertFalse(is_name_disallowed("tree", "fs", ["write", "compiler.*"]))

    def test_empty_patterns(self):
        self.assertFalse(is_name_disallowed("tree", "fs", []))
