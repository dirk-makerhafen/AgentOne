"""Admin for the WorkspaceModel."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.workspace import WorkspaceModel


@admin.register(WorkspaceModel)
class WorkspaceAdmin(admin.ModelAdmin):
    """Admin for workspace configurations."""
