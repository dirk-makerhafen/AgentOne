"""Admin for the Project model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.project import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin for projects."""
