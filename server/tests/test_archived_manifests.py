import shutil
import tempfile
from pathlib import Path

from django.test import TestCase

from registry.install_repo import InstallRepo
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.management.commands.reload_all import _archive_missing_globals
from runtime.agents.agents import Agents
from runtime.skill.skills import Skills
from server.models.agents.agent import AgentModel
from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion
from server.tests.helpers import AgentMdTestMixin


class ArchiveMissingGlobalsTest(TestCase):
    """Global rows without a manifest are archived, never deleted."""

    def test_archives_only_unseen_top_level_rows(self):
        seen_agent = AgentModel.objects.create(name="seen-agent")
        stale_agent = AgentModel.objects.create(name="stale-agent")
        child_agent = AgentModel.objects.create(
            name="child-agent", parent_agent=stale_agent
        )
        seen_skill = SkillModel.objects.create(name="seen-skill")
        stale_skill = SkillModel.objects.create(name="stale-skill")
        child_skill = SkillModel.objects.create(
            name="child-skill", parent_skill=stale_skill
        )

        _archive_missing_globals({"seen-agent"}, {"seen-skill"})

        for row in (seen_agent, stale_agent, child_agent, seen_skill, stale_skill, child_skill):
            row.refresh_from_db()
        self.assertFalse(seen_agent.is_archived)
        self.assertTrue(stale_agent.is_archived)
        self.assertFalse(child_agent.is_archived)
        self.assertFalse(seen_skill.is_archived)
        self.assertTrue(stale_skill.is_archived)
        self.assertFalse(child_skill.is_archived)

    def test_collections_hide_archived_rows(self):
        active = AgentModel.objects.create(name="active-agent")
        archived = AgentModel.objects.create(name="archived-agent", is_archived=True)
        active_skill = SkillModel.objects.create(name="active-skill")
        archived_skill = SkillModel.objects.create(
            name="archived-skill", is_archived=True
        )

        self.assertIn(active, Agents().root())
        self.assertNotIn(archived, Agents().root())
        self.assertIn(active_skill, Skills().root())
        self.assertNotIn(archived_skill, Skills().root())
        self.assertNotIn(archived, Agents().all())
        self.assertNotIn(archived_skill, Skills().all())

    def test_archived_agent_is_not_user_visible(self):
        agent = AgentModel.objects.create(name="hidden-agent", is_archived=True)
        self.assertFalse(agent.is_user_visible)


class UnarchiveOnReloadTest(AgentMdTestMixin, TestCase):
    """A manifest that reappears on disk unarchives its row."""

    @classmethod
    def setUpTestData(cls):
        cls.setup_global_tasks()
        cls.setup_install_repo()

    @classmethod
    def tearDownClass(cls):
        cls.teardown_install_repo()
        super().tearDownClass()

    def test_agent_loader_unarchives(self):
        agent, _ = self.load_agent("base")
        AgentModel.objects.filter(pk=agent.pk).update(is_archived=True)
        agent.refresh_from_db()
        self.assertTrue(agent.is_archived)

        reloaded, _ = self.load_agent("base")
        self.assertFalse(reloaded.is_archived)

    def test_skill_loader_unarchives(self):
        root = Path(tempfile.mkdtemp())
        try:
            source = root / "source"
            skill_dir = source / "skills" / "demo"
            skill_dir.mkdir(parents=True)
            (skill_dir / "skill.md").write_text(
                "---\nname: demo\ndescription: demo skill\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            repo = InstallRepo(repo_path=root / "install")
            repo.source_root = source
            repo.sync()

            skill = SkillModel.objects.create(name="demo")
            version = SkillModelVersion.objects.create(
                skill=skill, commit=repo.tree_sha(skill_dir)
            )
            SkillModel.objects.filter(pk=skill.pk).update(
                latest_skill_version=version, is_archived=True
            )
            skill.refresh_from_db()
            self.assertTrue(skill.is_archived)

            load_skill_manifest(skill_dir / "skill.md", install_repo=repo)
            skill.refresh_from_db()
            self.assertFalse(skill.is_archived)
        finally:
            shutil.rmtree(root, ignore_errors=True)
