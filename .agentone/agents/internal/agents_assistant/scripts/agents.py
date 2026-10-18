"""Agent collection tools for the agents_assistant agent.

All tools are bound: the managed scope is the global agents plus the
calling session's project agents (agent names are globally unique, so
single-agent work never needs disambiguation). Listing the collection
and collection health belong here; working on ONE agent (describe,
usage, versions) belongs to ``agent_assistant``. Creating or editing
agent manifests belongs to ``project_assistant``. Every tool returns a
``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def _scoped_agents(_session: Session):
    """Global agents plus the session project's own agents, ordered by name."""
    from runtime.agents.agents import Agents

    return Agents(parent_project=_session.get_project()).all()


def _agent_info(agent) -> dict[str, Any]:
    version = agent.latest_agent_version
    try:
        project_name = agent.parent_project.name if agent.parent_project else None
    except Exception:
        project_name = None
    try:
        parent_name = agent.parent_agent.name if agent.parent_agent else None
    except Exception:
        parent_name = None
    return {
        "name": agent.name,
        "path": getattr(agent, "manifest_dir", "") or "",
        "project": project_name,
        "parent_agent": parent_name,
        "kind": "subagent" if parent_name else "root",
        "visibility": version.visibility if version is not None else None,
        "version_number": version.version_number if version is not None else 0,
    }


def list_agents(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the agents visible in your managed scope, ordered by name.

    Global agents are visible everywhere; project agents only in their
    own project scope. Each entry flags root vs subagent and visibility.

    Returns:
        ``(True, {"status": "success", "agents": [...], "count": int,
        "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        agents = list(_scoped_agents(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agents: {e}"}

    project = _session.get_project()
    scope = f"global + project {project.name}" if project is not None else "global"
    return True, {
        "status": "success",
        "agents": [_agent_info(a) for a in agents],
        "count": len(agents),
        "scope": scope,
    }


def agents_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Count the agents in your managed scope: by visibility and by kind.

    Returns:
        ``(True, {"status": "success", "total": int,
        "by_visibility": {...}, "roots": int, "subagents": int})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        agents = list(_scoped_agents(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agents: {e}"}
    by_visibility: dict[str, int] = {}
    roots = 0
    for agent in agents:
        info = _agent_info(agent)
        vis = info["visibility"] or "unset"
        by_visibility[vis] = by_visibility.get(vis, 0) + 1
        if info["kind"] == "root":
            roots += 1
    return True, {
        "status": "success",
        "total": len(agents),
        "by_visibility": by_visibility,
        "roots": roots,
        "subagents": len(agents) - roots,
    }


def _validate_item_name(name: str, kind: str):
    """Validate a new agent/skill name. Returns ``(True, name)`` or ``(False, error)``."""
    import re

    clean = (name or "").strip()
    if not clean:
        return False, {"status": "error", "message": f"A {kind} name is required."}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", clean):
        return False, {
            "status": "error",
            "message": f"Invalid {kind} name '{clean}'. Use letters, digits, '-' or '_' (start with a letter or digit).",
        }
    return True, clean


def create_agent(
    _session: Session,
    name: str,
    description: str = "",
    model: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Create a new agent manifest in your managed scope.

    Writes ``<scope>/agents/<name>/agent.md`` (YAML frontmatter + body).
    Project scope writes into the project's ``.agentone/`` tree, global
    scope into ``~/.agentone/agents/``. The agent appears after the next
    manifest reload.

    Args:
        name: New agent name (required, globally unique).
        description: Short description (also used as the initial body).
        model: AI model identifier (optional, e.g. 'gemma4:26b').

    Returns:
        ``(True, {"status": "success", "name": str, "path": str,
        "scope": str, "note": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.agents.agent import AgentModel
    from runtime.paths import project_manifest_dir, user_agents_dir

    ok, clean = _validate_item_name(name, "agent")
    if not ok:
        return False, clean
    if AgentModel.objects.filter(name=clean).exists():
        return False, {
            "status": "error",
            "message": f"An agent named '{clean}' already exists. Pick another name.",
        }
    project = _session.get_project()
    if project is not None:
        base = project_manifest_dir(project) / "agents" / clean
        scope = f"project {project.name}"
    else:
        base = user_agents_dir() / clean
        scope = "global"
    manifest = base / "agent.md"
    if manifest.exists():
        return False, {
            "status": "error",
            "message": f"'{manifest}' already exists. Pick another name.",
        }
    body = (description or "").strip() or f"Agent {clean}."
    lines = ["---", f"name: {clean}"]
    if (description or "").strip():
        lines.append(f"description: {(description or '').strip()}")
    if (model or "").strip():
        lines.append(f"model: {(model or '').strip()}")
    lines += ["---", body, ""]
    try:
        base.mkdir(parents=True, exist_ok=True)
        manifest.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        return False, {"status": "error", "message": f"Could not write agent manifest: {e}"}
    return True, {
        "status": "success",
        "name": clean,
        "path": manifest.as_posix(),
        "scope": scope,
        "note": "Applies on the next manifest reload — tell the user to reload.",
    }


def refresh_from_disk(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Reload all agents visible in the managed scope from disk."""
    from pathlib import Path

    from runtime.paths import agentone_root, agentone_home, project_manifest_dir
    from registry.loader.load_agent_manifest import load_agent_manifest
    from registry.loader.utils import find_agent_md_files
    from registry.install_repo import InstallRepo

    project = _session.get_project()
    details: list[dict[str, Any]] = []
    errors: list[str] = []
    roots: list[tuple[Path, Any, InstallRepo]] = []
    if project is not None:
        md = project_manifest_dir(project)
        roots.append((md, project, InstallRepo.for_project(project.name, source_root=md)))
    else:
        roots.append((agentone_root(), None, InstallRepo.for_global(source_root=agentone_root())))
        roots.append((agentone_home(), None, InstallRepo.for_user(source_root=agentone_home())))

    for root, proj, repo in roots:
        agents_dir = root / "agents"
        if not agents_dir.is_dir():
            continue
        try:
            repo.sync()
        except Exception as e:  # pylint: disable=broad-exception-caught
            errors.append(f"sync {root}: {e}")
            continue
        for agent_md in find_agent_md_files(agents_dir):
            try:
                load_agent_manifest(agent_md, install_repo=repo, parent_project=proj, details=details)
            except Exception as e:  # pylint: disable=broad-exception-caught
                errors.append(f"{agent_md}: {e}")

    return (len(errors) == 0, {
        "status": "success" if not errors else "partial",
        "details": details,
        "errors": errors,
    })
