"""Single-skill tools for the skill_assistant agent.

All tools are bound to the calling session's workspace: the
skill_assistant session runs with its workspace set to the folder holding
that skill's ``skill.md`` (see ``Skill.get_assistant_session``), so the
skill is resolved from the workspace path — ``skill_usage`` takes NO
skill name. ``skills_for_agent`` looks up a *different* agent's effective
skills, so it keeps its agent argument. Reading and editing the
``skill.md`` itself is done with the filesystem tools, not with a
describe tool.
Collection operations (list, assign, unassign) belong to
``skills_assistant``. Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from runtime.script_helpers import agent_row, skill_row
from runtime.session.session import Session

#: How many recent load_skill calls to scan for usage attribution. The
#: scan is newest-first and stops at this cap, so usage counts are
#: "within recent history", not lifetime totals.
USAGE_SCAN_CAP = 500


def _normalize_dir(value: Any) -> str:
    """Normalize a directory path for comparison (no I/O)."""
    try:
        text = str(value or "").strip()
        if not text:
            return ""
        return Path(text).expanduser().as_posix().rstrip("/") or ""
    except Exception:
        return ""


def _scoped_skills(_session: Session):
    """Global skills plus the session project's own skills, ordered by name."""
    from runtime.skill.skills import Skills

    return Skills(parent_project=_session.get_project()).all()


def _resolve_skill(_session: Session):
    """Find the skill whose manifest folder is this session's workspace.

    Returns ``(True, skill)`` or ``(False, error_dict)``. When several
    rows share the folder (reloaded into multiple scopes), the session
    project's own row wins over the global one.
    """
    from server.models.skills.skill import SkillModel

    workspace = None
    try:
        workspace = _session.workspace
    except Exception:
        workspace = None
    ws_path = _normalize_dir(getattr(workspace, "path", None))
    if not ws_path:
        return False, {
            "status": "error",
            "message": (
                "This assistant session is not bound to a skill folder "
                "(no workspace). Open the assistant from a skill instead."
            ),
        }
    candidates = list(SkillModel.objects.filter(manifest_dir=ws_path))
    if not candidates:
        # Fall back to realpath comparison (symlinked home dirs, etc.).
        try:
            real = os.path.realpath(ws_path)
        except Exception:
            real = ""
        if real:
            for cand in SkillModel.objects.exclude(manifest_dir=""):
                try:
                    if os.path.realpath(cand.manifest_dir or "") == real:
                        candidates.append(cand)
                except Exception:
                    continue
    if not candidates:
        return False, {
            "status": "error",
            "message": (
                f"No skill found for this session's workspace '{ws_path}'. "
                "Open the assistant from a skill instead."
            ),
        }
    if len(candidates) == 1:
        return True, candidates[0]
    project = _session.get_project()
    if project is not None:
        local = [s for s in candidates if s.parent_project_id == project.pk]
        if local:
            return True, local[0]
    else:
        shared = [s for s in candidates if s.parent_project_id is None]
        if shared:
            return True, shared[0]
    return True, candidates[0]


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not (agent_name or "").strip():
        return None, "An agent name is required."
    agent = AgentModel.objects.filter(name=agent_name.strip()).first()
    if agent is None:
        return None, f"No agent named '{agent_name}'. Use get_available_agents to list them."
    return agent, None


def _load_skill_calls() -> list:
    """Recent ``load_skill`` task calls, newest first (capped)."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.task_definition import TaskDefinition

    td = TaskDefinition.objects.filter(name="load_skill").first()
    if td is None:
        return []
    return list(
        AgentTaskCall.objects.filter(task_definition=td)
        .select_related("session", "session_version")
        .order_by("-pk")[:USAGE_SCAN_CAP]
    )


def _call_skill_name(call) -> str:
    """Extract the skill name from a load_skill call's stored arguments."""
    try:
        args = call.carguments_json or {}
    except Exception:
        return ""
    if isinstance(args, dict):
        direct = args.get("skill_name", "")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        for value in args.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
    return ""


def skill_usage(_session: Session, limit: int = 10) -> tuple[bool, dict[str, Any]]:
    """Report how THIS skill is used: load counts by agent and recent loads.

    The skill is the one whose manifest folder is this session's
    workspace — no name argument.

    Scans recent ``load_skill`` calls (newest-first, capped) and
    attributes the ones naming this skill — use it to judge whether a
    skill is actually adopted, by whom, and where. Assignment (who CAN
    load it) lives in the agents' manifests — read them with the
    filesystem tools; this is who DOES.

    Args:
        limit: Max recent loads to detail (1-50, default 10).

    Returns:
        ``(True, {"status": "success", "skill": str, "total_loads": int,
        "scanned": int, "by_agent": {...}, "recent": [...]})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, skill = _resolve_skill(_session)
    if not ok:
        return False, skill
    try:
        limit = max(1, min(int(limit or 10), 50))
    except (TypeError, ValueError):
        return False, {"status": "error", "message": "limit must be a number."}
    try:
        calls = _load_skill_calls()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not read skill usage: {e}"}
    matching = [c for c in calls if _call_skill_name(c) == skill.name]
    by_agent: dict[str, int] = {}
    recent = []
    for call in matching:
        try:
            agent_name = call.session_version.agent.name
        except Exception:
            agent_name = None
        if agent_name:
            by_agent[agent_name] = by_agent.get(agent_name, 0) + 1
        if len(recent) < limit:
            try:
                session_name = call.session.name if call.session_id else None
            except Exception:
                session_name = None
            try:
                created = call.created_at.isoformat() if call.created_at else None
            except Exception:
                created = None
            recent.append({
                "created_at": created,
                "agent": agent_name,
                "session": session_name,
                "status": call.status,
            })
    by_agent = dict(sorted(by_agent.items(), key=lambda kv: (-kv[1], kv[0])))
    return True, {
        "status": "success",
        "skill": skill.name,
        "total_loads": len(matching),
        "scanned": len(calls),
        "by_agent": by_agent,
        "recent": recent,
    }


def skills_for_agent(_session: Session, agent_name: str) -> tuple[bool, dict[str, Any]]:
    """List the skills effectively available to one agent.

    Shows the skills on the agent's latest version (what the agent can
    actually load), restricted to skills visible in your scope. This
    inspects a *different* agent than your own skill, so it keeps its
    agent argument.

    Args:
        agent_name: Name of the agent (required).

    Returns:
        ``(True, {"status": "success", "agent": str, "skills": [...]})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    agent, error = _resolve_agent(agent_name)
    if error:
        return False, {"status": "error", "message": error}
    version = agent.latest_agent_version
    if version is None:
        return False, {"status": "error", "message": f"Agent '{agent.name}' has no version yet."}
    visible_ids = set(_scoped_skills(_session).values_list("pk", flat=True))
    skills = []
    try:
        for sv in version.skill_versions.all().select_related("skill"):
            try:
                skill = sv.skill
            except Exception:
                continue
            if skill is None or skill.pk not in visible_ids:
                continue
            skills.append({
                "name": skill.name,
                "description": sv.description or "",
                "version_number": sv.version_number,
            })
    except Exception as e:
        return False, {"status": "error", "message": f"Could not read agent skills: {e}"}
    skills.sort(key=lambda s: s["name"].lower())
    return True, {"status": "success", "agent": agent.name, "skills": skills, "count": len(skills)}


def list_skills(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List THIS skill's child skills, ordered by name.

    The skill is the one whose manifest folder is this session's
    workspace — no name argument. Base path ``<skill_dir>/skills/``.

    Returns:
        ``(True, {"status": "success", "skill": str, "skills": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.skill.skills import Skills

    ok, skill = _resolve_skill(_session)
    if not ok:
        return False, skill
    try:
        children = list(Skills(parent_skill=skill).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list child skills: {e}"}
    return True, {
        "status": "success",
        "skill": skill.name,
        "skills": [skill_row(s) for s in children],
        "count": len(children),
        "scope": f"{_normalize_dir(skill.manifest_dir)}/skills/",
    }


def list_agents(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the agents owned by THIS skill, ordered by name.

    The skill is the one whose manifest folder is this session's
    workspace — no name argument. Base path ``<skill_dir>/agents/``.

    Returns:
        ``(True, {"status": "success", "skill": str, "agents": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.agents.agents import Agents

    ok, skill = _resolve_skill(_session)
    if not ok:
        return False, skill
    try:
        agents = list(Agents(parent_skill=skill).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list skill agents: {e}"}
    return True, {
        "status": "success",
        "skill": skill.name,
        "agents": [agent_row(a) for a in agents],
        "count": len(agents),
        "scope": f"{_normalize_dir(skill.manifest_dir)}/agents/",
    }


def skill_details(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Show THIS skill's key details in one call: identity, version,
    load totals, and children counts.

    The skill is the one whose manifest folder is this session's
    workspace — no name argument. This returns what the file alone
    cannot: version identity, live load totals, and assignment counts.
    Use `skill_usage` / `list_*` for the full breakdowns.

    Returns:
        ``(True, {"status": "success", details...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.agents.agents import Agents
    from runtime.skill.skills import Skills

    ok, skill = _resolve_skill(_session)
    if not ok:
        return False, skill
    try:
        version = skill.latest_skill_version
    except Exception:
        version = None
    try:
        project_name = skill.parent_project.name if skill.parent_project else None
    except Exception:
        project_name = None
    try:
        calls = _load_skill_calls()
        total_loads = sum(1 for c in calls if _call_skill_name(c) == skill.name)
    except Exception:
        total_loads = 0
    try:
        agents_count = Agents(parent_skill=skill).all().count()
    except Exception:
        agents_count = 0
    try:
        child_skills_count = Skills(parent_skill=skill).all().count()
    except Exception:
        child_skills_count = 0
    users: list[str] = []
    try:
        if version is not None:
            seen = set()
            for av in version.used_by_agent_versions.all().select_related("agent"):
                try:
                    agent_name = av.agent.name
                except Exception:
                    continue
                if agent_name not in seen:
                    seen.add(agent_name)
                    users.append(agent_name)
            users.sort()
    except Exception:
        pass
    return True, {
        "status": "success",
        "name": skill.name,
        "path": skill.manifest_dir or "",
        "project": project_name,
        "version_number": version.version_number if version is not None else 0,
        "total_loads": total_loads,
        "agents_count": agents_count,
        "child_skills_count": child_skills_count,
        "used_by_agents": users,
        "scope": f"{_normalize_dir(skill.manifest_dir)}/",
    }
