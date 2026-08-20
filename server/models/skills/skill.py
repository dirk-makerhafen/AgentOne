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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(default="", max_length=255, help_text="")
    latest_skill_version = models.ForeignKey(SkillModelVersion,default=None,null=True,on_delete=models.SET_NULL,related_name="related_newest_skill")

    parent_agent = models.ForeignKey("server.AgentModel",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")
    parent_project = models.ForeignKey("server.Project",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")
    parent_skill = models.ForeignKey("self",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="related_skills")

