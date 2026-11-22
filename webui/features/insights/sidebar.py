def build_sidebar_context(request, project_id, ctx):
    ctx["insight_tabs"] = [
        ("dashboard", "Dashboard"),
        ("analytics", "Analytics"),
        ("providers", "Providers"),
        ("models", "Models"),
    ]


def sidebar_keys(context):
    # This sidebar only renders static tab labels; neither providers nor models
    # appear in it, so observing either model would refetch it for nothing.
    return ()


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("insights", sidebar_keys)
