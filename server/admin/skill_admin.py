from django.contrib import admin
from server.models.skills.skill import SkillModel

from server.models.skills.skill_version import SkillModelVersion

@admin.register(SkillModel)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at",  'name', 'parent_project', 'parent_agent', 'parent_skill'  )
    

@admin.register(SkillModelVersion)
class SkillVersionAdmin(admin.ModelAdmin):
    pass
