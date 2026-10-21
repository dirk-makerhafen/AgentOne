"""Admin for the Project model."""
from django.contrib import admin

from server.models.project import Project
from server.models.workspace import WorkspaceModel


class WorkspaceInline(admin.TabularInline):
    """Read-only inline listing a project's workspaces."""

    model: type[WorkspaceModel] = WorkspaceModel
    fk_name: str = "parent_project"
    extra: int = 0
    fields: tuple[str, ...] = ("name", "path", "agentone_dir", "updated_at")
    readonly_fields: tuple[str, ...] = ("name", "path", "agentone_dir", "updated_at")
    show_change_link: bool = True
    can_delete: bool = False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin for projects."""

    list_display: tuple[str, ...] = (
        "id", "name", "main_workspace", "agentone_dir", "git_ref", "updated_at",
    )
    list_filter: tuple[str, ...] = ("created_at",)
    search_fields: tuple[str, ...] = ("name", "description", "agentone_dir", "git_url")
    ordering: tuple[str, ...] = ("-updated_at",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at", "path")
    raw_id_fields: tuple[str, ...] = ("main_workspace",)
    inlines: list = [WorkspaceInline]
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("Folder", {
            "fields": ("main_workspace", "path", "agentone_dir"),
            "description": "A project's folder is its primary workspace; "
            "agentone_dir blank defaults to ~/.agentone/projects/<name>.",
        }),
        ("Git Source", {"fields": ("git_url", "git_ref")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
