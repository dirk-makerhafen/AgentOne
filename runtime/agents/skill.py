from __future__ import annotations
from typing import TYPE_CHECKING

from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion

class Skill():
    def __init__(self, skill_model: SkillModel, pinned_skill_version: SkillModelVersion|None = None):
        self.model = skill_model
        self._pinned_skill_version = pinned_skill_version

    @property
    def name(self): 
        return self.model.name
    
    @property
    def description(self): 
        return self.get_version_model().description
    @property
    def commit(self): 
        return self.get_version_model().commit
    @property
    def path(self): 
        return self.get_version_model().path
    @property
    def version_number(self): 
        return self.get_version_model().version_number

    @property
    def created_at(self): 
        return self.get_version_model().created_at

    def get_version_model(self) -> SkillModelVersion:
        if self._pinned_skill_version:
            return self._pinned_skill_version 
        return self.model.latest_skill_version 
    
    def all_versions(self):
        pass
