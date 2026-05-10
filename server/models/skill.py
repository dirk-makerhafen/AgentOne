from django.db import models

class Skill(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    name  = models.CharField(default="", max_length=255, help_text="")
    latest_skill_version = models.ForeignKey("server.SkillVersion", default=None, null=True, on_delete=models.SET_NULL, related_name='related_newest_skill')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_skills')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='related_skills')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    parent_skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='related_skills')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

    
class SkillVersion(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='versions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills

    description = models.TextField(max_length=1024, default="")
    commit = models.TextField(max_length=1024, default="")

    path  = models.CharField(default="", max_length=255, help_text="")
