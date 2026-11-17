def build_sidebar_context(request, project_id, ctx):
    return


def sidebar_keys(context):
    return ("Project",)


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("projects", sidebar_keys)
