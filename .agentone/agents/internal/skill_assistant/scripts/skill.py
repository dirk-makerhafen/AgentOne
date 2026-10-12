"""Single-skill tools for the skill_assistant agent.

All tools are bound and take the skill's ``name``: they describe ONE
skill, report its usage, and show one agent's effective skills — all
within the skills visible in the calling session's scope (global skills
plus the session project's own). Collection operations (list, assign,
unassign) belong to ``skills_assistant``. Every tool returns a
``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q

from runtime.session.session import Session

#: How many recent load_skill calls to scan for usage attribution. The
#: scan is newest-first and stops at this cap, so usage counts are
#: "within recent history", not lifetime totals.
USAGE_SCAN_CAP = 500


def _session_project(_session: Session) -> Any:
    """Return the project this session belongs to, or ``None`` for global."""
    model = getattr(_session, "model", None)
    return getattr(model, "parent_project", None) if model else None


def _scoped_skills(_session: Session):
    """Global skills plus the session project's own skills, ordered by name."""
    from server.models.skills.skill import SkillModel

    project = _session_project(_session)
    qs = SkillModel.objects.all()
    if project is not None:
        qs = qs.filter(Q(parent_project=project) | Q(parent_project__isnull=True))
    else:
        qs = qs.filter(parent_project__isnull=True)
    return qs.select_related("latest_skill_version", "parent_project").order_by("name")


def _latest_version(skill):
    try:
        return skill.latest_skill_version
    except Exception:
        return None


def _skill_info(skill) -> dict[str, Any]:
    version = _latest_version(skill)
    try:
        project_name = skill.parent_project.name if skill.parent_project else None
    except Exception:
        project_name = None
    return {
        "id": skill.pk,
        "name": skill.name,
        "project": project_name,
        "description": (version.description if version else "") or "",
        "path": (version.path if version else "") or "",
        "version_number": version.version_number if version else 0,
    }


def _resolve_skill(_session: Session, name: str):
    """Find one skill by name in scope (project-local wins over global)."""
    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A skill name is required."}
    matches = list(_scoped_skills(_session).filter(name=name))
    if not matches:
        return False, {"status": "error", "message": f"No skill named '{name}' in this scope."}
    project = _session_project(_session)
    if len(matches) > 1 and project is not None:
        local = [s for s in matches if s.parent_project_id == project.pk]
        if local:
            return True, local[0]
    if len(matches) > 1:
        return False, {
            "status": "error",
            "message": f"Multiple skills named '{name}'. Tell the user to pick one by project.",
            "projects": [getattr(s.parent_project, "name", None) for s in matches],
        }
    return True, matches[0]


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not (agent_name or "").strip():
        return None, "An agent name is required."
    agent = AgentModel.objects.filter(name=agent_name.strip()).first()
    if agent is None:
        return None, f"No agent named '{agent_name}'. Use get_available_agents to list them."
    return agent, None


def describe_skill(_session: Session, name: str) -> tuple[bool, dict[str, Any]]:
    """Show ONE skill in full: description, version, path, and which agents use it.

    Args:
        name: Name of the skill (required).

    Returns:
        ``(True, {"status": "success", skill..., "used_by_agents": [...]})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, skill = _resolve_skill(_session, name)
    if not ok:
        return False, skill
    version = _latest_version(skill)
    users: list[str] = []
    try:
        if version is not None:
            agent_versions = version.used_by_agent_versions.all().select_related("agent")
            seen = set()
            for av in agent_versions:
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
    info = _skill_info(skill)
    info.update({"status": "success", "used_by_agents": users})
    return True, info


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


def skill_usage(_session: Session, name: str, limit: int = 10) -> tuple[bool, dict[str, Any]]:
    """Report how ONE skill is used: load counts by agent and recent loads.

    Scans recent ``load_skill`` calls (newest-first, capped) and
    attributes the ones naming this skill — use it to judge whether a
    skill is actually adopted, by whom, and where. Assignment (who CAN
    load it) is ``describe_skill``; this is who DOES.

    Args:
        name: Name of the skill (required).
        limit: Max recent loads to detail (1-50, default 10).

    Returns:
        ``(True, {"status": "success", "skill": str, "total_loads": int,
        "scanned": int, "by_agent": {...}, "recent": [...]})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, skill = _resolve_skill(_session, name)
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
    actually load), restricted to skills visible in your scope.

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
