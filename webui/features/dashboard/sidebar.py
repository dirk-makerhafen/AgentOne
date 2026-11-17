"""Dashboard sidebar (shares chats data/keys)."""

from webui.features.chats.sidebar import build_sidebar_context, sidebar_keys


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("dashboard", sidebar_keys)
