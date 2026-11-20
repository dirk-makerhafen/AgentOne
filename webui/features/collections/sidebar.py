from server.models.collections.data_collection import DataCollection


def build_sidebar_context(request, project_id, ctx):
    ctx["sidebar_collections"] = list(
        DataCollection.objects.select_related("parent_project").order_by("name")
    )


def sidebar_keys(context):
    # Rows render the parent project name.
    return ("DataCollection", "Project")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("collections", sidebar_keys)
