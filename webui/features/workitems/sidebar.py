from server.models.project import Project
from server.models.workitems.enums import WorkItemStatus
from server.models.workitems.work_item import WorkItem


def build_sidebar_context(request, project_id, ctx):
    raw_project = request.GET.get("project", "")
    selected_project = int(raw_project) if raw_project.isdigit() else project_id
    qs = WorkItem.objects.select_related("assigned_agent").order_by("-priority", "created_at")
    if selected_project is not None:
        qs = qs.filter(project_id=selected_project)
    items = list(qs[:400])
    counts = {value: 0 for value, _ in WorkItemStatus.choices}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    ctx.update(
        {
            "sidebar_workitems": items,
            "sidebar_workitem_counts": counts,
            "sidebar_workitem_columns": [
                {"value": value, "label": label, "count": counts.get(value, 0)}
                for value, label in WorkItemStatus.choices
            ],
            "projects": list(Project.objects.order_by("name")),
            "selected_project": selected_project,
            "terminal_count": counts.get(WorkItemStatus.DONE, 0) + counts.get(WorkItemStatus.CANCELLED, 0),
        }
    )


def sidebar_keys(context):
    return ("WorkItem", "Project")


def register_sidebar_component():
    from webui.core.components import register_section_sidebar

    register_section_sidebar("workitems", sidebar_keys)
