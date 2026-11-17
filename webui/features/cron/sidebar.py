from server.models.cron import Cronjob


def build_sidebar_context(request, project_id, ctx):
    qs = Cronjob.objects.filter(is_archived=False)
    if project_id is not None:
        qs = qs.filter(parent_project_id=project_id)
    ctx["sidebar_cronjobs"] = list(
        qs.select_related("agent", "parent_project").order_by("-is_active", "name")
    )


def sidebar_keys(context):
    return ("Cronjob",)


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("cron", sidebar_keys)
