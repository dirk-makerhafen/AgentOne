from django.contrib import admin
from server.models.project import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    pass
