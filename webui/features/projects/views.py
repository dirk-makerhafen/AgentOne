"""Projects: overview, detail and create."""

from __future__ import annotations

from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from server.models.project import Project
from server.models.workspace import WorkspaceModel
from webui.core.assistants import assistant_overview_context, assistant_panel_context
from webui.core.layout import render_page


def projects(request):
    rows = list(Project.objects.order_by("name"))
    agent_counts = dict(
        Project.objects.annotate(total=Count("child_agents")).values_list("pk", "total")
    )
    session_counts = dict(
        Project.objects.annotate(total=Count("child_sessions")).values_list("pk", "total")
    )
    work_counts = dict(
        Project.objects.annotate(total=Count("work_items")).values_list("pk", "total")
    )
    for project in rows:
        project.agent_total = agent_counts.get(project.pk, 0)
        project.session_total = session_counts.get(project.pk, 0)
        project.work_total = work_counts.get(project.pk, 0)
    context = {"projects": rows}
    context.update(assistant_overview_context("projects"))
    return render_page(request, "projects", "projects/list.html", context)


@require_POST
def project_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("webui:projects")
    project = Project.objects.create(
        name=name,
        description=(request.POST.get("description") or "").strip(),
        git_url=(request.POST.get("git_url") or "").strip(),
    )
    return redirect("webui:project", project_id=project.pk)


def project_detail(request, project_id: int):
    project = get_object_or_404(Project, pk=project_id)
    context = {
        "project": project,
        "dashboard_content": _project_dashboard_content(project),
        "workspaces": list(project.workspaces.order_by("name")),
        "agents": list(project.child_agents.select_related("latest_agent_version").order_by("name")),
        "sessions": list(
            project.child_sessions.select_related("latest_session_version__agent")
            .order_by("-last_active_at")[:30]
        ),
        "crons": list(project.child_crons.filter(is_archived=False).order_by("name")),
        "skills": list(project.related_skills.order_by("name")),
        "session_count": project.child_sessions.count(),
        "work_items": list(
            project.work_items.select_related("assigned_agent").order_by("-priority", "created_at")[:40]
        ),
        "collections": list(project.data_collections.order_by("name")),
        "workspace_options": list(WorkspaceModel.objects.order_by("name")),
        "manifest_in_workspace": _manifest_in_workspace(project),
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_panel_context("project", project, request.GET.get("assistant_session")))
    return render_page(request, "projects", "projects/detail.html", context,
                       active_id=project.pk)



def _project_dashboard_content(project) -> str:
    """Return raw markdown for the project dashboard/index.md (or empty)."""
    path = getattr(project, "dashboard_index", None)
    if path is None:
        return ""
    try:
        if not path.is_file():
            return ""
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    try:
        import frontmatter

        post = frontmatter.loads(raw)
        content = (post.content or "").strip()
        return content if content else raw.strip()
    except Exception:  # pylint: disable=broad-exception-caught
        return raw.strip()


def _manifest_in_workspace(project: Project) -> bool:
    """True when the project's manifests live inside its main workspace."""
    workspace = getattr(project, "main_workspace", None)
    if workspace is None:
        return False
    try:
        from pathlib import Path

        return Path(project.get_agentone_dir()).resolve() == (
            Path(workspace.path) / ".agentone"
        ).resolve()
    except Exception:  # pylint: disable=broad-exception-caught
        return False


@require_POST
def project_edit(request, project_id: int):
    project = get_object_or_404(Project, pk=project_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect(f"/app/projects/{project.pk}?error=name")

    raw_workspace = (request.POST.get("main_workspace") or "").strip()
    workspace = (
        WorkspaceModel.objects.filter(pk=int(raw_workspace)).first()
        if raw_workspace.isdigit()
        else None
    )
    manifest_in_workspace = request.POST.get("manifest_in_workspace") == "on"
    git_url = (request.POST.get("git_url") or "").strip()

    try:
        from runtime.paths import central_project_dir, ensure_private_dir
        from pathlib import Path

        if manifest_in_workspace and workspace is not None:
            manifest = Path(workspace.path) / ".agentone"
        else:
            manifest = central_project_dir(name)
        ensure_private_dir(manifest)
    except OSError:
        return redirect(f"/app/projects/{project.pk}?error=write")

    project.atomic_update(
        name=name,
        description=(request.POST.get("description") or "").strip(),
        main_workspace=workspace,
        agentone_dir=manifest.as_posix(),
        git_url=git_url,
    )
    project.refresh_from_db()
    try:
        from registry.loader.load_project_folder import load_scope_dir

        load_scope_dir(manifest, project)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return redirect("webui:project", project_id=project.pk)
