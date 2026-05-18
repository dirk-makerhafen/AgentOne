from django.contrib import admin
from server.models.workspace import WorkspaceModel

@admin.register(WorkspaceModel)
class WorkspaceAdmin(admin.ModelAdmin):
    pass
