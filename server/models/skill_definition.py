from django.db import models
from django_enum import EnumField
from .content import GenericContent # Assuming content.py is in the same models directory

# Defines the structure for a declaratively defined agent/skill.
# This will store metadata parsed from SKILL.md files.
class SkillDefinition(models.Model):
    # Unique identifier derived from the markdown file name or a user-specified alias
    skill_slug = models.CharField(max_length=100, unique=True, help_text="A unique identifier for the skill (e.g., 'obsidian-search').")
    
    # The human-readable, long-form name
    name = models.CharField(max_length=200, help_text="The name used in the UI/System output.")
    
    # Detailed description of what the skill does
    description = models.TextField(help_text="A detailed explanation of the skill's capabilities.")
    
    # The core logic/tool provided by the skill. Can point to a specific internal method
    # or just be a generic instruction set.
    tool_description = models.TextField(null=True, blank=True)
    
    # Optional: A Python path or Class reference if the skill needs specific initialization logic
    # Example: "app.modules.ObsidianClient"
    target_source = models.CharField(max_length=255, null=True, blank=True, help_text="The module/class to instantiate for core logic.")

    # Key attributes for system compatibility
    requires_auth = models.BooleanField(default=False, help_text="Does this skill require external authentication (e.g., API key)?")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.skill_slug

    class Meta:
        verbose_name = "Skill Definition"
        verbose_name_plural = "Skill Definitions"
