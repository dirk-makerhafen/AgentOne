from django.contrib import admin
from server.models.skill import Skill

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    pass
