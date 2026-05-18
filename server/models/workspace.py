from django.db import models

class WorkspaceModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name  = models.CharField(default="", max_length=255, help_text="")
    description  = models.TextField(default="", max_length=10000, help_text="")
    path   = models.CharField(max_length=255, help_text="")


