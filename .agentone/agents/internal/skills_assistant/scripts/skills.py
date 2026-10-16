"""Skill collection tools for the skills_assistant agent.

All tools are bound: the managed scope is the global skills plus the
calling session's project skills. Listing the collection and assigning
or unassigning skills on agents belong here; working on ONE skill
(describe, usage, per-agent skills) belongs to ``skill_assistant``.
Every tool returns a ``(bool, dict)`` tuple.

Assignment edits the agent's *latest version* live. This is a runtime
override: the next manifest reload recomputes assignments from
``agent.md`` files, so a permanent change also needs an ``agent.md``
edit (via the project_assistant).
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def _scoped_skills(_session: Session):
    """Global skills plus the session project's own skills, ordered by name."""
    from runtime.skill.skills import Skills

    return Skills(parent_project=_session.get_project()).all()


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
        "manifest_dir": getattr(skill, "manifest_dir", "") or "",
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

    project = _session.get_project()
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


def list_skills(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the skills visible in your managed scope, ordered by name.

    Global skills are visible everywhere; project skills only in their
    own project scope.

    Returns:
        ``(True, {"status": "success", "skills": [...], "count": int,
        "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        skills = list(_scoped_skills(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list skills: {e}"}

    project = _session.get_project()
    scope = f"global + project {project.name}" if project is not None else "global"
    return True, {
        "status": "success",
        "skills": [_skill_info(s) for s in skills],
        "count": len(skills),
        "scope": scope,
    }


def assign_skill(_session: Session, agent_name: str, skill_name: str) -> tuple[bool, dict[str, Any]]:
    """Give an agent a skill, effective immediately.

    This edits the agent's latest version live. It is a runtime override:
    the next manifest reload recomputes assignments from ``agent.md``
    files, so for a permanent change also edit the agent's ``skills:``
    list (via the project_assistant) and reload. Deep analysis of ONE
    skill belongs to ``skill_assistant``.

    Args:
        agent_name: Name of the agent (required).
        skill_name: Name of the skill in your scope (required).

    Returns:
        ``(True, {"status": "success", "agent": str, "skill": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    agent, error = _resolve_agent(agent_name)
    if error:
        return False, {"status": "error", "message": error}
    ok, skill = _resolve_skill(_session, skill_name)
    if not ok:
        return False, skill
    version = agent.latest_agent_version
    if version is None:
        return False, {"status": "error", "message": f"Agent '{agent.name}' has no version yet."}
    skill_version = _latest_version(skill)
    if skill_version is None:
        return False, {"status": "error", "message": f"Skill '{skill.name}' has no version yet."}
    try:
        version.skill_versions.add(skill_version)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not assign skill: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "skill": skill.name,
        "note": "Live until the next manifest reload — edit the agent's skills: list for a permanent change.",
    }


def unassign_skill(_session: Session, agent_name: str, skill_name: str) -> tuple[bool, dict[str, Any]]:
    """Take a skill away from an agent, effective immediately.

    Same reload caveat as ``assign_skill``: lasting removal needs the
    skill dropped from the agent's ``skills:`` list (via the
    project_assistant) and a reload.

    Args:
        agent_name: Name of the agent (required).
        skill_name: Name of the skill in your scope (required).

    Returns:
        ``(True, {"status": "success", "agent": str, "skill": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    agent, error = _resolve_agent(agent_name)
    if error:
        return False, {"status": "error", "message": error}
    ok, skill = _resolve_skill(_session, skill_name)
    if not ok:
        return False, skill
    version = agent.latest_agent_version
    if version is None:
        return False, {"status": "error", "message": f"Agent '{agent.name}' has no version yet."}
    skill_version = _latest_version(skill)
    if skill_version is None:
        return False, {"status": "error", "message": f"Skill '{skill.name}' has no version yet."}
    try:
        if not version.skill_versions.filter(pk=skill_version.pk).exists():
            return False, {"status": "error", "message": f"Agent '{agent.name}' does not have skill '{skill.name}'."}
        version.skill_versions.remove(skill_version)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not unassign skill: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "skill": skill.name,
        "note": "Live until the next manifest reload — edit the agent's skills: list for a permanent change.",
    }


def _validate_item_name(name: str, kind: str):
    """Validate a new skill name. Returns ``(True, name)`` or ``(False, error)``."""
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


def create_skill(
    _session: Session,
    name: str,
    description: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Create a new skill manifest in your managed scope.

    Writes ``<scope>/skills/<name>/skill.md`` (YAML frontmatter + body).
    Project scope writes into the project's ``.agentone/`` tree, global
    scope into ``~/.agentone/skills/``. The skill appears after the next
    manifest reload.

    Args:
        name: New skill name (required, unique in this scope).
        description: Short description (also used as the initial body).

    Returns:
        ``(True, {"status": "success", "name": str, "path": str,
        "scope": str, "note": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.paths import project_manifest_dir, user_skills_dir
    from runtime.skill.skills import Skills

    ok, clean = _validate_item_name(name, "skill")
    if not ok:
        return False, clean
    project = _session.get_project()
    if Skills(parent_project=project).all().filter(name=clean).exists():
        where = f"in project {project.name}" if project is not None else "globally"
        return False, {
            "status": "error",
            "message": f"A skill named '{clean}' already exists {where}. Pick another name.",
        }
    if project is not None:
        base = project_manifest_dir(project) / "skills" / clean
        scope = f"project {project.name}"
    else:
        base = user_skills_dir() / clean
        scope = "global"
    manifest = base / "skill.md"
    if manifest.exists():
        return False, {
            "status": "error",
            "message": f"'{manifest}' already exists. Pick another name.",
        }
    body = (description or "").strip() or f"Skill {clean}."
    lines = ["---", f"name: {clean}"]
    if (description or "").strip():
        lines.append(f"description: {(description or '').strip()}")
    lines += ["---", body, ""]
    try:
        base.mkdir(parents=True, exist_ok=True)
        manifest.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        return False, {"status": "error", "message": f"Could not write skill manifest: {e}"}
    return True, {
        "status": "success",
        "name": clean,
        "path": manifest.as_posix(),
        "scope": scope,
        "note": "Applies on the next manifest reload — tell the user to reload.",
    }
