from django.db import models

class SkillModelVersion(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skill = models.ForeignKey("server.SkillModel", default=None, null=True, on_delete=models.CASCADE, related_name='versions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills

    description = models.TextField(max_length=1024, default="")
    commit = models.TextField(max_length=1024, default="")

    path  = models.CharField(default="", max_length=255, help_text="")
    version_number = models.IntegerField(default=0)
