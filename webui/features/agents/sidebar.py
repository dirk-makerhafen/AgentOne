from server.models.agents.agent import AgentModel


def build_sidebar_context(request, project_id, ctx):
    qs = AgentModel.objects.filter(is_archived=False)
    if project_id is not None:
        qs = qs.filter(parent_project_id=project_id)
    ctx["sidebar_agents"] = list(
        qs.select_related("latest_agent_version", "parent_project").order_by("name")
    )


def sidebar_keys(context):
    return ("AgentModel", "Project.root")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("agents", sidebar_keys)
