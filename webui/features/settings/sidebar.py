def build_sidebar_context(request, project_id, ctx):
    ctx["settings_tabs"] = [
        ("appearance", "Appearance"),
        ("preferences", "Preferences"),
        ("providers", "Providers"),
        ("system", "System"),
    ]


def sidebar_keys(context):
    return ()


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("settings", sidebar_keys)
