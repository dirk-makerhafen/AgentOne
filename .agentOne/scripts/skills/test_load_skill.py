"""
Tests for the ``load_skill`` tool.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skills.load_skill import load_skill


class TestLoadSkill(unittest.TestCase):
    """Tests for the load_skill bound tool."""

    def setUp(self):
        self.session = MagicMock()
        self.skill_version = MagicMock()
        self.skill_version.skill.name = "test-skill"
        self.skill_version.description = "A test skill"
        self.skill_version.version_number = 1

    def test_skill_not_found(self):
        """Returns error when skill is not found or not allowed."""
        self.session.get_skill.return_value = None
        success, result = load_skill(self.session, "nonexistent")
        self.assertFalse(success)
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"])

    def test_skill_no_path(self):
        """Returns error when skill version has no file path."""
        self.skill_version.path = ""
        self.session.get_skill.return_value = self.skill_version
        success, result = load_skill(self.session, "test-skill")
        self.assertFalse(success)
        self.assertEqual(result["status"], "error")
        self.assertIn("no file path", result["message"])

    def test_skill_file_missing(self):
        """Returns error when the skill.md file does not exist on disk."""
        self.skill_version.path = "/tmp/nonexistent/skill.md"
        self.session.get_skill.return_value = self.skill_version
        success, result = load_skill(self.session, "test-skill")
        self.assertFalse(success)
        self.assertEqual(result["status"], "error")
        self.assertIn("not found on disk", result["message"])

    def test_skill_success(self):
        """Returns parsed frontmatter and body for a valid skill.md."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("---\nname: test-skill\ndescription: A test skill\n---\n\n# Hello\n\nWorld\n")
            skill_path = f.name

        try:
            self.skill_version.path = skill_path
            self.session.get_skill.return_value = self.skill_version
            success, result = load_skill(self.session, "test-skill")
            self.assertTrue(success)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["name"], "test-skill")
            self.assertEqual(result["description"], "A test skill")
            self.assertEqual(result["version"], 1)
            self.assertEqual(result["metadata"]["name"], "test-skill")
            self.assertEqual(result["metadata"]["description"], "A test skill")
            self.assertIn("Hello", result["body"])
            self.assertIn("World", result["body"])
        finally:
            os.unlink(skill_path)

    def test_skill_bad_frontmatter(self):
        """Returns error when the skill.md has invalid YAML frontmatter."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("---\ninvalid: [unclosed\n---\n\nBody\n")
            skill_path = f.name

        try:
            self.skill_version.path = skill_path
            self.session.get_skill.return_value = self.skill_version
            success, result = load_skill(self.session, "test-skill")
            self.assertFalse(success)
            self.assertEqual(result["status"], "error")
            self.assertIn("Failed to parse", result["message"])
        finally:
            os.unlink(skill_path)


if __name__ == "__main__":
    unittest.main()
