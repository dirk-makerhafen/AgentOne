from __future__ import annotations

from typing import Any

from django.db import models

from server.models.base_model import ObservableMixin, Observables
from server.models.skills.skill_version import SkillModelVersion


class SkillModel(ObservableMixin, models.Model):
    """A skill group that versions its configuration over time."""

    class SkillModelObservables(Observables):
        """Explicit observable keys for an SkillModel (IDE autocomplete)."""
        @property
        def child_agents(self):
            return f"AgentModel.parent_skill:{self.model.pk}"
        @property
        def child_skills(self):
            return f"SkillModel.parent_skill:{self.model.pk}"
        @property
        def versions(self):
            return f"SkillModelVersion.skill:{self.model.pk}"
        @property
        def task_definitions(self):
            return f"TaskDefinition.parent_skill:{self.model.pk}"

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(default="", max_length=255, help_text="")
    latest_skill_version = models.ForeignKey(SkillModelVersion,default=None,null=True,on_delete=models.SET_NULL,related_name="related_newest_skill")

    parent_agent = models.ForeignKey("server.AgentModel",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")
    parent_project = models.ForeignKey("server.Project",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")
    parent_skill = models.ForeignKey("self",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")
    # manifest_dir: directory holding this skill's skill.md (set by the
    # loader; blank for rows predating the field or created ad hoc).
    manifest_dir: str = models.CharField(max_length=1024, default="", blank=True)


    def refresh_from_disk(self, details=None) -> None:
        """Reload this skill (and child scripts) from disk."""
        from pathlib import Path

        from runtime.paths import model_manifest_dir
        from registry.loader.load_skill_manifest import load_skill_manifest
        from runtime.refresh import install_repo_for_path

        skill_dir = model_manifest_dir(self, "skill", self.name, self.parent_project)
        md = skill_dir / "skill.md"
        if not md.is_file() and (self.manifest_dir or "").strip():
            md = Path(self.manifest_dir) / "skill.md"
            skill_dir = md.parent
        if details is None:
            details = []
        _source_root, install_repo = install_repo_for_path(skill_dir)
        try:
            install_repo.sync()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        load_skill_manifest(
            md,
            install_repo=install_repo,
            parent_project=self.parent_project,
            parent_agent=self.parent_agent,
            details=details,
        )
        self.refresh_from_db()
