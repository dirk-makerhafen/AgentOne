def build_sidebar_context(request, project_id, ctx):
    ctx["insight_tabs"] = [
        ("dashboard", "Dashboard"),
        ("analytics", "Analytics"),
        ("providers", "Providers"),
        ("models", "Models"),
    ]


def sidebar_keys(context):
    return ("ApiProvider", "AiModel")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("insights", sidebar_keys)
