from server.models.skills.skill import SkillModel


def build_sidebar_context(request, project_id, ctx):
    show_archived = request.GET.get("archived") == "1"
    qs = SkillModel.objects.filter(is_archived=show_archived)
    if project_id is not None:
        qs = qs.filter(parent_project_id=project_id)
    ctx["sidebar_skills"] = list(
        qs.select_related(
            "parent_agent", "parent_project", "parent_skill", "latest_skill_version"
        ).order_by("name")
    )
    ctx["show_archived"] = show_archived


def sidebar_keys(context):
    # Rows render the parent agent/skill/project names.
    return ("SkillModel", "AgentModel", "Project")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("skills", sidebar_keys)
