"""Single framework-administration entry point for the AgentOne agent.

Projects, workspaces and cron jobs are DB-canonical and are managed here
directly. Agents and skills are manifest-defined, but their live DB state is
readable here (list/stats/details; skills also supports ``load`` for the full
skill body); writes go through manifest files edited by ``coding``, followed by
``admin_tool(scope="system", action="reload")``.
Everything the model needs at call time is reachable through
``admin_tool(scope=..., action="help")`` so no per-action tool descriptions
have to be preloaded into the context.

The implementation is split across ``admin_{common,help,projects,workspaces,
cronjobs,agents,skills,system}.py``.
"""
from __future__ import annotations

from typing import Any

from admin_common import _err
from admin_help import HELP, help_result, resolve_action, resolve_scope
from admin_projects import _projects
from admin_workspaces import _workspaces
from admin_cronjobs import _cronjobs
from admin_agents import _agents
from admin_skills import _skills
from admin_system import _system


_HANDLERS = {
    "projects": _projects,
    "workspaces": _workspaces,
    "cronjobs": _cronjobs,
    "agents": _agents,
    "skills": _skills,
    "system": _system,
}


def admin_tool(_session: Any, scope: str, action: str, **kwargs: Any) -> tuple[bool, dict[str, Any]]:
    """Administer the AgentOne framework on the user's behalf.

    One tool for framework administration. Projects, workspaces and cron jobs
    are DB-canonical and are managed directly here. Agents and skills are
    manifest-defined, but their live state lives in the DB and can be
    *inspected* here (list/stats/details; `skills.load` also returns the skill's
    full markdown body). To create or edit an agent, its tools, or a skill:
    delegate the filesystem manifest edit to `coding` in
    the right `.agentone/` tree, then call
    `admin_tool(scope="system", action="reload")` so the framework projects
    the files into the live DB. Never edit the DB copies directly.

    `scope` selects the area, `action` the operation. Scopes:

      projects   help, list, stats, details, create, reload, dashboard
      workspaces help, list, stats, details, create, rename, update, dashboard, create_chat
      cronjobs   help, list, stats, details, create, update, set_active, set_archived, runs
      agents     help, list, stats, details — reads of the live DB; writes via manifests + reload
      skills     help, list, stats, load, details — reads of the live DB; writes via manifests + reload
      workitems  help only — use the dedicated `workitems.*` tools
      system     help, reload — reload manifests into the DB after file edits
      help       index of all scopes

    Projects and workspaces can be targeted explicitly with `project_pk` /
    `project_name` and `workspace_pk` / `workspace_name`. Prefer these when the
    session's inferred page scope is not the target; an explicit id or name
    wins over the session binding. Names may be partial if unambiguous.

    Every scope accepts `action="help"`: it returns that scope's valid
    actions and their keyword arguments. Use it to discover the exact
    arguments at the moment you need them instead of guessing, and instead
    of preloading a large tool surface into every session.

    Args:
        scope: Area to administer (see above); 'help' returns the index.
        action: Operation; 'help' describes one scope.

    Extra keyword arguments are scope- and action-specific — discover them
    with `admin_tool(scope=..., action="help")`. All calls return
    `(success, result)` with a `status` of `success` or `error`.
    """
    key = resolve_scope(scope)
    if key is None:
        return _err(f"Unknown scope '{scope}'. Valid scopes: {', '.join(sorted(HELP))}")
    if key == "help":
        return help_result("help")

    normalized_action = resolve_action(action)
    if normalized_action == "help":
        return help_result(key)

    handler = _HANDLERS.get(key)
    if handler is None:
        return _err(
            f"Scope '{key}' has no state-changing actions. Call action='help' for guidance.",
            notes=HELP[key]["notes"],
        )
    if normalized_action not in HELP[key]["actions"]:
        return _err(
            f"Unknown action '{action}' for scope '{key}'. Valid: "
            f"{', '.join(sorted(HELP[key]['actions']))}",
        )
    try:
        return handler(_session, normalized_action, kwargs)
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _err(f"{key}.{normalized_action} failed: {e}")

