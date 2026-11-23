"""Guided chats launched from Settings → System for local-change cleanup.

These chats are deliberately ordinary sessions (not rightbar assistants): the
user sees the whole conversation and can keep working after the job is done.
The prompt carries the exact paths and safety rules so the agent does not have
to guess what "fix the dirty tree" means.
"""

from __future__ import annotations

import uuid

from webui.core.layout import default_agent

_MIGRATION_AGENT = "coding"
_CONFLICT_AGENT = "coding"


def _paths_block(paths: list[str]) -> str:
    if not paths:
        return "- (no paths reported)"
    return "\n".join(f"- `{path}`" for path in paths[:40])


def start_guided_session(*, prefix: str, description: str, prompt: str, agent_name: str) -> int | None:
    """Create a chat, dispatch *prompt* as its first user message, return its pk."""
    from server.models.agents.agent import AgentModel  # pylint: disable=import-outside-toplevel

    agent = AgentModel.objects.filter(
        name=agent_name, is_archived=False, latest_agent_version__isnull=False
    ).order_by("-pk").first()
    if agent is None:
        agent = default_agent()
    if agent is None or agent.latest_agent_version is None:
        return None

    name = f"{prefix}-{uuid.uuid4().hex[:8]}"
    session_version = agent.latest_agent_version.get_or_create_session(
        name=name,
        display_name=name,
        description=description,
    )
    session = session_version.session
    session.get_runtime().add_user_message(prompt)
    return session.pk


def start_migration_session(paths: list[str], *, install_dir: str, home_dir: str) -> int | None:
    """Move install-dir manifest edits to the user scope, then clean the tree."""
    prompt = (
        "The AgentOne update on Settings → System is blocked by local changes under the "
        "install checkout's `.agentone/` folder:\n"
        f"{_paths_block(paths)}\n\n"
        f"In AgentOne, `{install_dir}/.agentone/` is the shipped global scope and is "
        "replaced on every update. Your own manifest/config edits belong in "
        f"`{home_dir}/` (for example `{install_dir}/.agentone/agents/foo/agent.md` → "
        f"`{home_dir}/agents/foo/agent.md`).\n\n"
        "Please:\n"
        f"1. Inspect each path above (`git -C {install_dir} status --porcelain`, "
        "`git diff`, file contents) and work out what change the user intended.\n"
        f"2. Copy/merge that content into the matching path under `{home_dir}/`. "
        "Create directories as needed. Do not overwrite unrelated files in the home "
        "scope; if a target already exists with different content, merge carefully or ask.\n"
        f"3. Verify the manifests load from the user scope (`venv/bin/python manage.py "
        f"reload_all` from `{install_dir}`).\n"
        "4. Revert only the migrated paths in the install checkout: `git restore -- "
        "<tracked paths>` and delete the untracked ones. Confirm "
        f"`git -C {install_dir} status --porcelain` is empty.\n"
        "5. Report exactly what you moved, what you reverted, and the final git status.\n\n"
        "Do not touch any other local changes or files outside these paths. If anything "
        "is ambiguous, ask before changing it."
    )
    return start_guided_session(
        prefix="migrate-local-manifests",
        description="Migrate local .agentone edits from the install directory to ~/.agentone",
        prompt=prompt,
        agent_name=_MIGRATION_AGENT,
    )


def start_conflict_session(
    *,
    conflicts: list[str],
    paths: list[str],
    stash_ref: str,
    preference: str = "",
) -> int | None:
    """Resolve a stash-pop conflict after the update pulled new code."""
    preference_text = {
        "local": "Prefer the local side (the stashed changes) for conflicting hunks.",
        "remote": "Prefer the remote side (the freshly updated AgentOne code) for conflicting hunks.",
    }.get(preference, "No side was preferred; decide per conflict and explain the trade-off.")
    prompt = f"""The automatic AgentOne update finished, but reapplying the local changes conflicted. The worktree is currently in a conflicted state.

Conflicted paths:
{_paths_block(conflicts)}

All locally changed paths before the update:
{_paths_block(paths)}

Git stash holding the original local changes: `{stash_ref}`. During `git stash pop`, `git show :2:<path>` is the updated remote side and `git show :3:<path>` is the local side.

Your task:
1. Inspect every conflicted path from both sides and resolve it. {preference_text}
   Keep any *non-conflicting* local changes exactly as they were reapplied.
2. `git add` the resolved paths, then `git reset` so the final result stays as ordinary uncommitted local changes (do not commit).
3. Only after every conflict is resolved and nothing was lost, drop the stash with `git stash drop {stash_ref}`.
4. Run a focused check (`venv/bin/python -m pytest ...` for touched Python code, or reload manifests for `.agentone/` changes) and report what you resolved and what remains."""
    return start_guided_session(
        prefix="resolve-update-conflict",
        description="Resolve conflicts from reapplying local changes after an AgentOne update",
        prompt=prompt,
        agent_name=_CONFLICT_AGENT,
    )
