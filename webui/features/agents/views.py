"""Agents: overview, detail and manifest CRUD."""

from __future__ import annotations

import shutil
from pathlib import Path

from django.http import HttpResponse
import yaml
from django.conf import settings
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from server.models.agents.agent import AgentModel
from server.models.providers.ai_model import AiModel
from server.models.project import Project
from server.models.sessions.session import SessionModel
from webui.core.assistants import assistant_overview_context, assistant_panel_context
from webui.core.shell import render_page

#: Reasoning-effort choices offered by the agent form.
REASONING_CHOICES = ("none", "minimal", "low", "medium", "high", "xhigh")


def _agent_scope_dir(project: Project | None, name: str) -> Path:
    """Directory that holds ``agents/<name>/agent.md`` for the chosen scope."""
    safe = str(name).strip().replace(" ", "_").replace("/", "_")
    if project is not None:
        try:
            return Path(project.get_agentone_dir()) / "agents" / safe
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return Path(settings.BASE_DIR) / ".agentone" / "agents" / safe


def _reload_scope(project: Project | None) -> None:
    """Re-sync the manifests for the scope that owns an agent."""
    try:
        if project is not None:
            from registry.loader.load_project_folder import load_scope_dir

            load_scope_dir(project.get_agentone_dir(), project)
        else:
            from registry.management.commands.reload_all import run_reload_all

            run_reload_all(str(settings.BASE_DIR))
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def _write_agent_manifest(agent_dir: Path, frontmatter: dict, body: str) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip(), "---"]
    if body:
        lines.extend(["", body])
    (agent_dir / "agent.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_agent_frontmatter(agent: AgentModel) -> tuple[Path, dict, str]:
    """Return ``(manifest_dir, frontmatter, body)`` for an agent (best effort)."""
    from runtime.paths import model_manifest_dir

    directory = model_manifest_dir(agent, "agent", agent.name, agent.parent_project)
    md = directory / "agent.md"
    if not md.is_file():
        return directory, {}, ""
    try:
        import frontmatter as frontmatter_lib

        post = frontmatter_lib.load(md)
        return directory, dict(post.metadata or {}), post.content or ""
    except Exception:  # pylint: disable=broad-exception-caught
        return directory, {}, ""


def agents(request) -> HttpResponse: 
    rows = list(
        AgentModel.objects.select_related(
            "latest_agent_version", "parent_project", "parent_agent", "parent_skill"
        ).order_by("is_archived", "name")
    )
    session_counts = dict(
        SessionModel.objects.filter(latest_session_version__agent__isnull=False)
        .values_list("latest_session_version__agent_id")
        .annotate(total=Count("pk"))
    )
    for agent in rows:
        agent.session_total = session_counts.get(agent.pk, 0)
    context = {
        "agents": rows,
        "archived_count": sum(1 for agent in rows if agent.is_archived),
        "models": list(AiModel.objects.order_by("name").values_list("name", flat=True)),
        "reasoning_choices": REASONING_CHOICES,
        "projects": list(Project.objects.order_by("name")),
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_overview_context("agents"))
    return render_page(request, "agents", "agents/list.html", context)


@require_POST
def agent_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("/app/agents?error=name")

    raw_project = (request.POST.get("parent_project") or "").strip()
    project = (
        Project.objects.filter(pk=int(raw_project)).first()
        if raw_project.isdigit()
        else None
    )
    agent_dir = _agent_scope_dir(project, name)
    if (agent_dir / "agent.md").exists():
        return redirect("/app/agents?error=exists")

    frontmatter: dict = {"name": name}
    extends = (request.POST.get("extends") or "").strip()
    if extends:
        frontmatter["extends"] = [
            part.strip() for part in extends.split(",") if part.strip()
        ]
    model = (request.POST.get("model") or "").strip()
    if model:
        frontmatter["model"] = model
    reasoning = (request.POST.get("reasoning_effort") or "").strip()
    if reasoning in REASONING_CHOICES:
        frontmatter["reasoningEffort"] = reasoning
    for field, key in (
        ("max_turns", "maxTurns"),
        ("max_unattended_turns", "maxUnattendedTurns"),
    ):
        raw = (request.POST.get(field) or "").strip()
        if raw.isdigit() and int(raw) > 0:
            frontmatter[key] = int(raw)

    try:
        _write_agent_manifest(
            agent_dir, frontmatter, (request.POST.get("description") or "").strip()
        )
    except OSError:
        return redirect("/app/agents?error=write")

    _reload_scope(project)
    agent = AgentModel.objects.filter(name=name).first()
    if agent is not None:
        return redirect("webui:agent", agent_id=agent.pk)
    return redirect("webui:agents")


def agent_detail(request, agent_id: int):
    agent = get_object_or_404(
        AgentModel.objects.select_related(
            "latest_agent_version", "parent_project", "parent_agent", "parent_skill"
        ),
        pk=agent_id,
    )
    version = agent.latest_agent_version
    versions = list(
        agent.related_agent_versions.order_by("-version_number", "-pk")[:40]
    )
    sessions = list(
        SessionModel.objects.filter(latest_session_version__agent=agent)
        .select_related("latest_session_version__workspace", "parent_project")
        .order_by("-last_active_at")[:25]
    )
    _manifest_dir, frontmatter, body = _read_agent_frontmatter(agent)
    capability_sections = _capability_sections(version)
    context = {
        "agent": agent,
        "version": version,
        "versions": versions,
        "sessions": sessions,
        "session_count": SessionModel.objects.filter(
            latest_session_version__agent=agent
        ).count(),
        "extends_names": list(getattr(version, "extends_agent_names", None) or []),
        "capability_sections": capability_sections,
        "child_agents": list(agent.child_agents.select_related("latest_agent_version")),
        "skills": list(agent.related_skills.order_by("name")),
        "crons": list(agent.related_cron.filter(is_archived=False).order_by("name")),
        "task_definitions": list(
            version.defined_task_versions.select_related("task_definition").order_by(
                "task_definition__name"
            )[:200]
        ) if version else [],
        "manifest": frontmatter,
        "manifest_body": body,
        "models": list(AiModel.objects.order_by("name").values_list("name", flat=True)),
        "reasoning_choices": REASONING_CHOICES,
        "projects": list(Project.objects.order_by("name")),
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_panel_context("agent", agent, request.GET.get("assistant_session")))
    return render_page(request, "agents", "agents/detail.html", context,
                       active_id=agent.pk)


def _capability_sections(version) -> list[dict]:
    if version is None:
        return []
    sections = []
    for title, allowed_attr, denied_attr in (
        ("Tools", "toolNames", "disallowedToolNames"),
        ("Tasks", "taskNames", "disallowedTaskNames"),
        ("Commands", "commandNames", "disallowedCommandNames"),
        ("Skills", "skillNames", "disallowedSkillNames"),
        ("Subagents", "subagentNames", "disallowedSubagentNames"),
    ):
        allowed = set(version.resolve_setting(allowed_attr) or [])
        denied = set(version.resolve_setting(denied_attr) or [])
        sections.append({
            "title": title,
            "rows": [
                {"name": name, "allowed": name not in denied}
                for name in sorted(allowed | denied)
            ],
        })
    return sections


@require_POST
def agent_edit(request, agent_id: int):
    agent = get_object_or_404(AgentModel, pk=agent_id)
    old_name = agent.name
    new_name = (request.POST.get("name") or "").strip() or old_name
    directory, frontmatter, body = _read_agent_frontmatter(agent)

    frontmatter = dict(frontmatter or {})
    frontmatter["name"] = new_name
    model = (request.POST.get("model") or "").strip()
    if model:
        frontmatter["model"] = model
    else:
        frontmatter.pop("model", None)
    reasoning = (request.POST.get("reasoning_effort") or "").strip()
    if reasoning in REASONING_CHOICES:
        frontmatter["reasoningEffort"] = reasoning
    for field, key in (
        ("max_turns", "maxTurns"),
        ("max_unattended_turns", "maxUnattendedTurns"),
        ("max_retries", "maxRetries"),
    ):
        raw = (request.POST.get(field) or "").strip()
        if raw.isdigit():
            frontmatter[key] = int(raw)
    description = (request.POST.get("description") or "").strip()

    target_dir = directory
    try:
        if new_name != old_name and directory.name == old_name:
            target_dir = directory.parent / new_name
            if target_dir.exists():
                return redirect(f"/app/agents/{agent.pk}?error=exists")
            directory.rename(target_dir)
        _write_agent_manifest(target_dir, frontmatter, description)
    except OSError:
        return redirect(f"/app/agents/{agent.pk}?error=write")

    _reload_scope(agent.parent_project)
    refreshed = AgentModel.objects.filter(name=new_name).first()
    if refreshed is not None:
        return redirect("webui:agent", agent_id=refreshed.pk)
    return redirect("webui:agents")


@require_POST
def agent_delete(request, agent_id: int):
    agent = get_object_or_404(AgentModel, pk=agent_id)
    directory, _frontmatter, _body = _read_agent_frontmatter(agent)
    delete_files = request.POST.get("delete_files") == "on"
    project = agent.parent_project
    agent.delete()
    if delete_files and directory.is_dir():
        try:
            shutil.rmtree(directory)
        except OSError:
            pass
        _reload_scope(project)
    return redirect("webui:agents")
