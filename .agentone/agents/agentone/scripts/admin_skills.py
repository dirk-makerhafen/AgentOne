"""DB-backed skill reads for the AgentOne admin_tool dispatcher.

Skills are defined by ``skill.md`` manifests, but the database is the live
view of them. This module only *inspects* that view. Creating or editing a
skill is a filesystem manifest edit followed by a framework reload — never a
state-changing action on this tool.
"""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project_for


def _scoped_skills(session: Any, project: Any = None):
    """Global skills plus *project*'s own skills, ordered by name."""
    from runtime.skill.skills import Skills

    return Skills(parent_project=project or session.get_project()).all()


def _skill_info(skill: Any) -> dict[str, Any]:
    try:
        version = skill.latest_skill_version
    except Exception:  # pylint: disable=broad-exception-caught
        version = None
    try:
        project_name = skill.parent_project.name if skill.parent_project else None
    except Exception:  # pylint: disable=broad-exception-caught
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


def _resolve_skill(session: Any, name: Any, project: Any = None):
    """Find one skill by name in scope (project-local wins). Returns ``(skill, error)``."""
    name = str(name or "").strip()
    if not name:
        return None, "A skill name is required (kwargs: name)."
    matches = list(_scoped_skills(session, project).filter(name=name))
    if not matches:
        return None, f"No skill named '{name}' in this scope."
    if len(matches) > 1 and project is not None:
        local = [s for s in matches if getattr(s, "parent_project_id", None) == project.pk]
        if local:
            return local[0], None
    if len(matches) > 1:
        return None, (
            f"Multiple skills named '{name}' — pass the scope explicitly or pick by project: "
            f"{[getattr(s.parent_project, 'name', None) for s in matches]}"
        )
    return matches[0], None


def _skills(session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    project, error = _scope_project_for(session, kwargs)
    if error:
        return _err(error)

    if action == "list":
        try:
            skills = list(_scoped_skills(session, project))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list skills: {e}")
        scope = f"global + project {project.name}" if project is not None else "global"
        return _ok(skills=[_skill_info(s) for s in skills], count=len(skills), scope=scope)

    if action == "stats":
        try:
            skills = list(_scoped_skills(session, project))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list skills: {e}")
        return _ok(
            total=len(skills),
            global_count=sum(1 for s in skills if getattr(s, "parent_project_id", None) is None),
            project_count=sum(1 for s in skills if getattr(s, "parent_project_id", None) is not None),
        )

    if action == "load":
        from runtime.skill.load_content import load_skill_content

        return load_skill_content(session, kwargs.get("name") or kwargs.get("skill_name"))

    if action == "details":
        skill, error = _resolve_skill(session, kwargs.get("name"), project)
        if error:
            return _err(error)
        from runtime.agents.agents import Agents
        from runtime.skill.skills import Skills
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.task_definition import TaskDefinition

        info = _skill_info(skill)
        try:
            call_args = []
            for td_name in ("load_skill", "admin_tool"):
                td = TaskDefinition.objects.filter(name=td_name).first()
                if td is None:
                    continue
                call_args.extend(
                    AgentTaskCall.objects.filter(task_definition=td)
                    .values_list("carguments_json", flat=True)[:200]
                )
            total_loads = sum(
                1 for args in call_args
                if isinstance(args, dict) and (
                    args.get("skill_name") == skill.name
                    or (args.get("scope") == "skills" and args.get("action") == "load"
                        and (args.get("name") or args.get("skill_name")) == skill.name)
                )
            )
        except Exception:  # pylint: disable=broad-exception-caught
            total_loads = 0
        try:
            agents_count = Agents(parent_skill=skill).all().count()
        except Exception:  # pylint: disable=broad-exception-caught
            agents_count = 0
        try:
            child_skills_count = Skills(parent_skill=skill).all().count()
        except Exception:  # pylint: disable=broad-exception-caught
            child_skills_count = 0
        users: list[str] = []
        try:
            version = skill.latest_skill_version
            if version is not None:
                seen = set()
                for av in version.used_by_agent_versions.all().select_related("agent"):
                    agent_name = av.agent.name
                    if agent_name not in seen:
                        seen.add(agent_name)
                        users.append(agent_name)
                users.sort()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return _ok(
            **info,
            total_loads=total_loads,
            agents_count=agents_count,
            child_skills_count=child_skills_count,
            used_by_agents=users,
        )

    return _err(f"Unknown action '{action}' for scope 'skills'")
