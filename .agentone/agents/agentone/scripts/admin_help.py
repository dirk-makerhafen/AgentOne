"""Runtime-discoverable help for admin_tool scopes/actions."""
from __future__ import annotations

from typing import Any

from admin_common import _normalize, _ok


# ---------------------------------------------------------------------------
# Runtime-discoverable reference. This is the authoritative answer to
# ``admin_tool(scope=..., action="help")`` — keep it in sync with the handlers.
# ---------------------------------------------------------------------------

HELP: dict[str, dict[str, Any]] = {
    "help": {
        "summary": "Index of admin scopes. Call admin_tool(scope='<scope>', action='help') for details.",
        "actions": {},
        "notes": [],
    },
    "projects": {
        "summary": "Register and inspect projects (DB-canonical; manifests live in the project's .agentone/ tree).",
        "actions": {
            "help": "Return this reference.",
            "list": "All registered projects; flags the current one.",
            "stats": "Per-project counts of agents, skills, cron jobs, workspaces and work items.",
            "details": "One project plus its owned resources. kwargs: project_pk? / project_name? / name? (defaults to current scope).",
            "create": "Register a project and scaffold its .agentone/ tree. kwargs: name, path? (or project_path?), description?, manifest_in_workspace? (default true), workspace_name?. A path creates/links a primary workspace folder.",
            "reload": "Reload a project's manifests from disk. kwargs: project_pk? / project_name? (defaults to current scope).",
            "dashboard": "Read or write <project>/.agentone/dashboard/index.md. kwargs: project_pk? / project_name?, content? (omit content to read).",
        },
        "notes": [
            "Projects are global: every registered project is visible from any session.",
            "Creating a project scaffolds folders only; agents/skills inside it are still manifest files edited by coding.",
        ],
    },
    "workspaces": {
        "summary": "Register and inspect workspaces (DB-canonical; nesting is determined by path prefix).",
        "actions": {
            "help": "Return this reference.",
            "list": "Workspaces in scope. kwargs: include_nested? (default true).",
            "stats": "Scope counts: total, top_level, nested.",
            "details": "One workspace, its nested children, sessions and scoped resources. kwargs: workspace_pk? / workspace_name? / name? (defaults to current).",
            "create": "Register an existing directory as a workspace. kwargs: name, path, description?, parent_workspace_pk?.",
            "rename": "kwargs: workspace_pk, name.",
            "update": "Edit description. kwargs: workspace_pk, description.",
            "dashboard": "Read or write <workspace>/.agentone/dashboard/index.md. kwargs: workspace_pk? / workspace_name?, content? (omit content to read).",
            "create_chat": "Open a chat session bound to the workspace. kwargs: workspace_pk? / workspace_name?, agent_name?, title?.",
        },
        "notes": [
            "In a project-bound session new workspaces are owned by that project; otherwise they are global.",
            "Ownership (parent_project) and path nesting are orthogonal; a nested path must sit inside its parent's path.",
            "An explicit workspace_pk/workspace_name targets that workspace even when it is outside the session's inferred scope.",
        ],
    },
    "cronjobs": {
        "summary": "Schedule and tune cron jobs (DB-canonical; no manifest files).",
        "actions": {
            "help": "Return this reference.",
            "list": "Jobs in scope. kwargs: include_archived? (default false).",
            "stats": "Active / paused / archived counts, total runs, next run.",
            "details": "One job's full configuration. kwargs: name (or pk).",
            "create": "Create an active job. kwargs: name, schedule, agent_name, message?, description?, session_mode?, session_name?, function_type?, function_name?, workspace_name?.",
            "update": "Change only the fields you pass. kwargs: name (or pk) plus any create field except name.",
            "set_active": "Pause or resume. kwargs: name (or pk), is_active.",
            "set_archived": "Archive or restore; history is kept. kwargs: name (or pk), archived? (default true).",
            "runs": "Recent dispatches, newest first. kwargs: name (or pk), limit? (default 20).",
        },
        "notes": [
            "Schedules: standard cron ('0 9 * * *'), shorthands ('@daily', '@hourly'), or 'every N min|hour' ('every 30m').",
            "function_type is '', 'task', 'tool' or 'command'; with a function target, message must be JSON matching that function's args.",
            "Archiving hides a job but keeps its run data; pausing is for temporary stops.",
        ],
    },
    "agents": {
        "summary": "Inspect agents in the live DB (manifest-defined; edits happen on disk + reload).",
        "actions": {
            "help": "Return this reference.",
            "list": "Agents in scope with version/visibility. kwargs: project_pk? / project_name? (defaults to current scope).",
            "stats": "Counts by visibility and root/subagent. kwargs: project_pk? / project_name?.",
            "details": "One agent's version and live usage counts. kwargs: name, project_pk? / project_name?.",
        },
        "notes": [
            "Reads come from the DB — the live projection of agent.md manifests.",
            "Explicit project_pk/project_name scopes these reads even from a global rightbar chat.",
            "To create/edit an agent or its tools, delegate the manifest edit to coding: <scope>/.agentone/agents/<name>/agent.md (and scripts/scripts.md).",
            "After the file edit, call admin_tool(scope='system', action='reload', folder='<root containing .agentone>') so the DB picks it up.",
        ],
    },
    "skills": {
        "summary": "Inspect skills in the live DB (manifest-defined; edits happen on disk + reload).",
        "actions": {
            "help": "Return this reference.",
            "list": "Skills in scope with version/description. kwargs: project_pk? / project_name? (defaults to current scope).",
            "stats": "Global vs project-owned counts. kwargs: project_pk? / project_name?.",
            "load": "Read one allowed skill's versioned skill.md (frontmatter metadata + body). kwargs: name (or skill_name).",
            "details": "One skill's version, usage and assigned agents. kwargs: name, project_pk? / project_name?.",
        },
        "notes": [
            "Reads come from the DB — the live projection of skill.md manifests.",
            "Explicit project_pk/project_name scopes these reads even from a global rightbar chat.",
            "Use 'load' to get the full skill instructions before following a procedure; 'details' only returns metadata.",
            "To create/edit a skill, delegate the manifest edit to coding: <scope>/.agentone/skills/<name>/skill.md (and its scripts/ folder).",
            "After the file edit, call admin_tool(scope='system', action='reload', folder='<root containing .agentone>') so the DB picks it up.",
        ],
    },
    "workitems": {
        "summary": "Work items already have dedicated tools; this tool does not manage them.",
        "actions": {"help": "Return this reference."},
        "notes": ["Use workitem_create / workitem_add_child / workitem_list / workitem_update directly."],
    },
    "system": {
        "summary": "Framework-wide actions, notably the manifest-to-DB reload.",
        "actions": {
            "help": "Return this reference.",
            "reload": "Load manifests from disk into the DB. kwargs: folder? (root containing .agentone/; defaults to the current scope).",
        },
        "notes": [
            "Call reload after any agent/skill manifest edit; until then the DB and these reads are stale.",
            "Projects, workspaces and cron jobs are DB-canonical and are never loaded from manifests.",
        ],
    },
}

SCOPE_ALIASES = {
    "": "help",
    "?": "help",
    "index": "help",
    "project": "projects",
    "workspace": "workspaces",
    "cronjob": "cronjobs",
    "cron_job": "cronjobs",
    "cron": "cronjobs",
    "agent": "agents",
    "skill": "skills",
    "workitem": "workitems",
    "work_item": "workitems",
}

ACTION_ALIASES = {
    "": "help",
    "?": "help",
    "get": "details",
    "describe": "details",
    "show": "details",
    "edit": "update",
    "modify": "update",
    "archive": "set_archived",
    "pause": "set_active",
    "resume": "set_active",
}


def resolve_scope(scope: Any) -> str | None:
    """Map a scope spelling (aliases included) to a canonical key."""
    key = _normalize(scope)
    key = SCOPE_ALIASES.get(key, key)
    return key if key in HELP else None


def resolve_action(action: Any) -> str:
    """Map an action spelling (aliases included) to a canonical key."""
    key = _normalize(action)
    return ACTION_ALIASES.get(key, key)


def help_result(scope: str) -> tuple[bool, dict[str, Any]]:
    entry = HELP[scope]
    if scope == "help":
        return _ok(
            scopes={key: value["summary"] for key, value in HELP.items() if key != "help"},
            hint="Call admin_tool(scope='<scope>', action='help') for that scope's actions and kwargs.",
        )
    return _ok(
        scope=scope,
        summary=entry["summary"],
        actions=entry["actions"],
        notes=entry["notes"],
    )

