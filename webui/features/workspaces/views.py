"""Workspaces (spaces): overview, detail, create, edit and delete."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from server.models.agents.agent import AgentModel
from server.models.project import Project
from server.models.sessions.session import SessionModel
from server.models.workspace import (
    WorkspaceModel,
    random_workspace_color,
    validate_workspace_color,
)
from webui.features.workspaces.access import (
    DEFAULTS,
    KEYS,
    SECTIONS,
    normalize_access,
)
from webui.core.assistants import assistant_overview_context, assistant_panel_context
from webui.features.workspaces.manifest import (
    STORAGES,
    detect_storage,
    ensure_manifest_dir,
    gitignore_has_agentone,
    storage_options,
)
from webui.core.layout import render_page, unique_session_name

log = logging.getLogger(__name__)
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_MANAGER_AGENT_NAME = "AgentOne"


def _access_from_post(request) -> dict:
    """Read the access editor's form fields into the model's JSON shape."""
    data: dict = {}
    for section in SECTIONS:
        default = request.POST.get(f"access_{section}_default", "allow")
        if default not in DEFAULTS:
            default = "allow"
        entry = {"default": default}
        for key in KEYS:
            raw = request.POST.get(f"access_{section}_{key}", "")
            entry[key] = [line.strip() for line in raw.splitlines() if line.strip()]
        data[section] = entry
    return data


def _parent_project(request) -> Project | None:
    raw = (request.POST.get("parent_project") or "").strip()
    return Project.objects.filter(pk=int(raw)).first() if raw.isdigit() else None


def workspace_directory_context(workspace, raw_path: str, log_context: str) -> dict:
    """List a workspace directory level while keeping resolved paths in-root."""
    if workspace is None or not workspace.path:
        return {
            "workspace_root": "",
            "workspace_relative_path": "",
            "workspace_parent_path": None,
            "workspace_entries": [],
            "workspace_error": "",
        }
    try:
        root = Path(workspace.path).expanduser().resolve(strict=True)
        if not root.is_dir():
            return {
                "workspace_root": str(root),
                "workspace_relative_path": "",
                "workspace_parent_path": None,
                "workspace_entries": [],
                "workspace_error": "Workspace path is not a directory.",
            }
        current = (root / raw_path).resolve(strict=True)
        if not current.is_dir() or not current.is_relative_to(root):
            return {
                "workspace_root": str(root),
                "workspace_relative_path": "",
                "workspace_parent_path": None,
                "workspace_entries": [],
                "workspace_error": "Directory is unavailable.",
            }
        entries = []
        for child in sorted(
            current.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())
        ):
            if child.name in ("__pycache__", ".DS_Store"):
                continue
            resolved = child.resolve(strict=True)
            if not resolved.is_relative_to(root):
                continue
            is_dir = resolved.is_dir()
            size = resolved.stat().st_size if resolved.is_file() else 0
            entries.append({
                "name": child.name,
                "is_dir": is_dir,
                "size": size,
                "size_label": _format_file_size(size) if not is_dir else "",
                "relative_path": resolved.relative_to(root).as_posix(),
            })
        relative = current.relative_to(root).as_posix()
        parent = current.parent.relative_to(root).as_posix() if current != root else None
        return {
            "workspace_root": str(root),
            "workspace_relative_path": relative if relative != "." else "",
            "workspace_parent_path": parent,
            "workspace_entries": entries,
            "workspace_error": "",
        }
    except (OSError, RuntimeError) as exc:
        log.warning("could not browse workspace %s: %s", log_context, exc)
        return {
            "workspace_root": "",
            "workspace_relative_path": "",
            "workspace_parent_path": None,
            "workspace_entries": [],
            "workspace_error": "Workspace directory could not be read.",
        }


def _format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# Shared folder browser ----------------------------------------------------
#
# The chat rightbar and the workspace detail page render the very same tree
# partial.  Only the URLs differ, so host views pass URL builders here and the
# partial stays free of any host-specific markup or logic.

_TREE_SURFACES = ("panel", "page")


def directory_url(url_name: str, args: list, path: str = "", *, param: str = "path",
             surface: str | None = None) -> str:
    """Build a directory URL with an optional path/surface query string."""
    params = {param: path} if path else {}
    if surface:
        params["surface"] = surface
    base = reverse(url_name, args=args)
    return f"{base}?{urlencode(params, safe='/')}" if params else base


def _directory_breadcrumbs(workspace, current: str, browse_url, push_url) -> list:
    """Root-to-current crumbs for the folder the tree is rooted at."""
    crumbs = [{
        "name": workspace.name,
        "url": browse_url(""),
        "push_url": push_url("") if push_url else "",
    }]
    parts = [part for part in current.split("/") if part]
    for index, part in enumerate(parts):
        path = "/".join(parts[:index + 1])
        crumbs.append({
            "name": part,
            "url": browse_url(path),
            "push_url": push_url(path) if push_url else "",
        })
    return crumbs


def workspace_tree_context(
    workspace,
    raw_path: str,
    log_context: str,
    *,
    surface: str,
    browse_url,
    push_url=None,
) -> dict:
    """Build the context for the shared folder tree, with host-supplied URLs."""
    context = workspace_directory_context(workspace, raw_path, log_context)
    surface = surface if surface in _TREE_SURFACES else "page"
    entries = []
    for entry in context["workspace_entries"]:
        entry = dict(entry)
        entry["children_url"] = (
            directory_url("webui:workspace_directory_children", [workspace.pk],
                     entry["relative_path"], surface=surface)
            if entry["is_dir"] else ""
        )
        entries.append(entry)
    context["workspace_entries"] = entries
    current = context["workspace_relative_path"]
    parent = context["workspace_parent_path"]
    context.update({
        "dir_surface": surface,
        "dir_breadcrumbs": _directory_breadcrumbs(workspace, current, browse_url, push_url),
        "dir_root_url": browse_url(""),
        "dir_parent_url": browse_url(parent) if parent is not None else "",
        "dir_parent_push_url": push_url(parent) if push_url and parent is not None else "",
        "dir_refresh_url": browse_url(current),
        "dir_refresh_push_url": push_url(current) if push_url else "",
    })
    return context


def workspace_directory(request, workspace_id: int):
    """Folder-browser fragment for the workspace detail page."""
    workspace = get_object_or_404(WorkspaceModel, pk=workspace_id)

    def browse_url(path):
        return directory_url("webui:workspace_directory", [workspace_id], path)

    def push_url(path):
        return directory_url("webui:workspace", [workspace_id], path, param="files")

    context = workspace_tree_context(
        workspace,
        request.GET.get("files", ""),
        f"{workspace_id} directory",
        surface="page",
        browse_url=browse_url,
        push_url=push_url,
    )
    return render(request, "workspaces/parts/directory_browser.html", {
        "workspace": workspace,
        **context,
    })


def workspace_directory_children(request, workspace_id: int):
    """Lazy-loaded children of one folder, shared by both host views."""
    workspace = get_object_or_404(WorkspaceModel, pk=workspace_id)
    context = workspace_directory_context(
        workspace,
        request.GET.get("path", ""),
        f"{workspace_id} tree children",
    )
    surface = request.GET.get("surface", "page")
    surface = surface if surface in _TREE_SURFACES else "page"
    entries = []
    for entry in context["workspace_entries"]:
        entry = dict(entry)
        entry["children_url"] = (
            directory_url("webui:workspace_directory_children", [workspace_id],
                     entry["relative_path"], surface=surface)
            if entry["is_dir"] else ""
        )
        entries.append(entry)
    return render(request, "workspaces/parts/directory_nodes.html", {
        "dir_entries": entries,
        "dir_surface": surface,
        "dir_error": context["workspace_error"],
    })


def workspaces(request):
    rows = list(
        WorkspaceModel.objects.select_related("parent_project").order_by("name")
    )
    context = {
        "workspaces": rows,
        "projects": list(Project.objects.order_by("name")),
        "storage_options": storage_options(),
        "access_form": normalize_access(None),
        "access_sections": SECTIONS,
        "access_keys": KEYS,
        "access_defaults": DEFAULTS,
    }
    context.update(assistant_overview_context("workspaces"))
    return render_page(request, "workspaces", "workspaces/list.html", context)


@require_POST
def workspace_create(request):
    name = (request.POST.get("name") or "").strip()
    path = (request.POST.get("path") or "").strip()
    if not name or not path:
        return redirect("webui:workspaces")
    color = (request.POST.get("color") or "").strip()
    if not _COLOR_RE.match(color):
        color = random_workspace_color()
    storage = (request.POST.get("storage") or "").strip()
    if storage not in STORAGES:
        storage = "user"
    parent_project = _parent_project(request)
    if storage == "project" and parent_project is None:
        storage = "user"
    workspace = WorkspaceModel(
        name=name,
        path=path,
        color=color,
        description=(request.POST.get("description") or "").strip(),
        parent_project=parent_project,
        access=_access_from_post(request),
    )
    manifest_dir = ensure_manifest_dir(
        workspace, storage, path,
        track_agentone=request.POST.get("track_agentone") == "on",
    )
    workspace.agentone_dir = manifest_dir or workspace.get_agentone_dir().as_posix()
    workspace.save()
    return redirect("webui:workspace", workspace_id=workspace.pk)



def _workspace_dashboard_content(workspace) -> str:
    """Return raw markdown for the workspace dashboard/index.md (or empty)."""
    path = getattr(workspace, "dashboard_index", None)
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


def workspace_detail(request, workspace_id: int):
    workspace = get_object_or_404(
        WorkspaceModel.objects.select_related("parent_project"), pk=workspace_id
    )
    sessions = list(
        SessionModel.objects.filter(latest_session_version__workspace=workspace)
        .select_related("latest_session_version__agent")
        .order_by("-last_active_at")[:30]
    )
    storage = detect_storage(workspace)

    def browse_url(path):
        return directory_url("webui:workspace_directory", [workspace_id], path)

    def push_url(path):
        return directory_url("webui:workspace", [workspace_id], path, param="files")

    files_context = workspace_tree_context(
        workspace,
        request.GET.get("files", ""),
        f"{workspace.pk} detail",
        surface="page",
        browse_url=browse_url,
        push_url=push_url,
    )
    context = {
        "workspace": workspace,
        "sessions": sessions,
        "dashboard_content": _workspace_dashboard_content(workspace),
        "crons": list(workspace.cron_jobs.filter(is_archived=False).order_by("name")),
        "access": normalize_access(workspace.access),
        "access_form": normalize_access(workspace.access),
        "access_sections": SECTIONS,
        "access_keys": KEYS,
        "access_defaults": DEFAULTS,
        "storage": storage,
        "storage_options": storage_options(),
        "track_agentone": (
            storage == "inline" and not gitignore_has_agentone(workspace.path)
        ),
        "projects": list(Project.objects.order_by("name")),
        "error": request.GET.get("error", ""),
        **files_context,
    }
    context.update(assistant_panel_context(
        "workspace", workspace, request.GET.get("assistant_session")
    ))
    return render_page(request, "workspaces", "workspaces/detail.html", context,
                       active_id=workspace.pk)


@require_POST
def workspace_manager_open(request, workspace_id: int):
    """Create a workspace-bound manager chat and open it in the chat view."""
    workspace = get_object_or_404(
        WorkspaceModel.objects.select_related("parent_project"), pk=workspace_id
    )
    agent = AgentModel.objects.filter(name=_MANAGER_AGENT_NAME).first()
    if agent is None or agent.latest_agent_version is None:
        return redirect(f"/app/workspaces/{workspace.pk}?error=manager-agent")

    name = unique_session_name(f"{_MANAGER_AGENT_NAME} - {workspace.name}")
    try:
        session_version = agent.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description="",
            workspace=workspace,
            group_key=f"assistant:{_MANAGER_AGENT_NAME}",
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not create workspace manager chat for %s", workspace.pk)
        return redirect(f"/app/workspaces/{workspace.pk}?error=manager-create")

    session = session_version.session
    if workspace.parent_project_id and session.parent_project_id != workspace.parent_project_id:
        session.parent_project = workspace.parent_project
        session.save(update_fields=["parent_project_id"])
    return redirect("webui:chat", session_id=session.pk)


@require_POST
def workspace_edit(request, workspace_id: int):
    workspace = get_object_or_404(WorkspaceModel, pk=workspace_id)
    name = (request.POST.get("name") or "").strip()
    path = (request.POST.get("path") or "").strip()
    color = (request.POST.get("color") or "").strip()
    if not name:
        return redirect(f"/app/workspaces/{workspace.pk}?error=name")
    if not path or not os.path.isdir(path):
        return redirect(f"/app/workspaces/{workspace.pk}?error=path")
    try:
        validate_workspace_color(color)
    except Exception:  # pylint: disable=broad-exception-caught
        return redirect(f"/app/workspaces/{workspace.pk}?error=color")

    storage = (request.POST.get("storage") or "").strip()
    if storage not in STORAGES:
        storage = detect_storage(workspace)
    if storage not in STORAGES:
        storage = "user"

    parent_project = _parent_project(request)
    if storage == "project" and parent_project is None:
        return redirect(f"/app/workspaces/{workspace.pk}?error=project")

    workspace.name = name
    workspace.description = (request.POST.get("description") or "").strip()
    workspace.path = path
    workspace.color = color
    workspace.access = _access_from_post(request)
    workspace.parent_project = parent_project

    try:
        manifest_dir = ensure_manifest_dir(
            workspace, storage, path,
            track_agentone=request.POST.get("track_agentone") == "on",
        )
    except OSError:
        return redirect(f"/app/workspaces/{workspace.pk}?error=write")
    workspace.agentone_dir = manifest_dir or workspace.get_agentone_dir().as_posix()
    workspace.save()
    return redirect("webui:workspace", workspace_id=workspace.pk)


@require_POST
def workspace_delete(request, workspace_id: int):
    workspace = get_object_or_404(WorkspaceModel, pk=workspace_id)
    workspace.delete()
    return redirect("webui:workspaces")
