from django.db import models

from server.models.content import GenericContent

class Cronjob(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name  = models.CharField(default="", max_length=255, help_text="")
    description  = models.TextField(default="", max_length=10000, help_text="")
    schedule   = models.CharField(max_length=2048, help_text="")
    prompt   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="related_cron_prompt")
    agent = models.ForeignKey("server.AgentModel", on_delete=models.CASCADE, related_name="related_cron", blank=True, null=True)
