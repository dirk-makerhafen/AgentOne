from server.models.workspace import WorkspaceModel
from webui.features.workspaces.sidebar_helper import build_workspace_tree


def build_sidebar_context(request, project_id, ctx):
    items = list(WorkspaceModel.objects.select_related("parent_project").order_by("name"))
    ctx["sidebar_workspaces"] = build_workspace_tree(items)


def sidebar_keys(context):
    return ("WorkspaceModel",)


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("workspaces", sidebar_keys)
