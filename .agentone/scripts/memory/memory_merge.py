"""Update memory manifests by delegating to the memory-manage agent.

When ``walk_memory`` reports items in ``needs_update``, this module creates
a memory-manage agent session, sends it a layer-specific prompt describing
the changed sources, waits for the LLM to process them, and returns the
result.

The actual merge (content processing) requires LLM reasoning — we can't
do it programmatically.  Each merge function constructs its own prompt
that explains the directory structure and what changed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from server.models.agents.agent import AgentModel
from runtime.session.session import Session


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------


def _create_memory_session(
    level: str, folder: str, sources: list[dict], session: Any = None
) -> Session | None:
    """Create a memory-manage agent session for the given level.

    Args:
        level: Synthesis level – ``"task"``, ``"agent"``, or ``"scope"``.
        folder: Path to the manifest directory.
        sources: List of changed source dicts from ``needs_update``.
        session: Optional caller session for workspace context.

    Returns:
        A Session object bound to the memory-manage agent, or None on failure.
    """
    try:
        agent = AgentModel.objects.get(name="memory-manage")
    except AgentModel.DoesNotExist:
        return None

    av = agent.latest_agent_version
    if av is None:
        return None

    # Determine workspace from the caller session or from the folder path
    workspace = None
    if session and hasattr(session, "workspace"):
        workspace = session.workspace

    sv = av.get_or_create_session(
        name=f"memory:{level}:{int(time.time())}",
        workspace=workspace,
        session_type="subsession",
        group_key=f"memory:{level}",
    )
    return Session(session_model=sv.session, pinned_session_version=sv)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _format_sources(sources: list[dict]) -> str:
    """Format a list of source dicts as a readable bullet list."""
    lines = []
    for src in sources:
        path = src.get("path", "?")
        stype = src.get("type", "?")
        pk = src.get("pk")
        changed = src.get("changed_chars", 0)
        last = src.get("last_processed_hash", "?")[:8]
        curr = src.get("current_hash", "?")[:8]
        parts = [f"- ``{path}``"]
        if stype:
            parts.append(f"({stype})")
        if pk is not None:
            parts.append(f"pk={pk}")
        if changed:
            parts.append(f"{changed} chars changed")
        parts.append(f"hash: {last} → {curr}")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "(none)"


def _build_task_prompt(folder: str, sources: list[dict]) -> str:
    """Build a prompt for the task level (``task_*`` directories)."""
    return (
        "Update the memory manifest at ``{folder}``.\n"
        "\n"
        "This is a task directory (``task_*``) inside an agent.  The\n"
        "``sessions/`` directory contains session report files\n"
        "(``reflections_*.md``, ``compactions_*.md``).\n"
        "\n"
        "The following source paths have changed (their content hashes\n"
        "differ from the last-processed snapshot):\n"
        "{sources}\n"
        "\n"
        "Read the existing ``.memory_sources.md`` manifest at\n"
        "``{folder}``, update the git commit hashes for the changed\n"
        "sources listed above, and write the manifest back.  Preserve\n"
        "all unchanged entries exactly as they are."
    ).format(folder=folder, sources=_format_sources(sources))


def _build_agent_prompt(folder: str, sources: list[dict]) -> str:
    """Build a prompt for the agent level (``agents/`` directories)."""
    return (
        "Update the memory manifest at ``{folder}``.\n"
        "\n"
        "This is an agent directory.  The ``tasks/`` directory contains\n"
        "task sub-directories, each with session reports.\n"
        "\n"
        "The following source paths have changed:\n"
        "{sources}\n"
        "\n"
        "Read the existing ``.memory_sources.md`` manifest at\n"
        "``{folder}``, update the git commit hashes for the changed\n"
        "sources listed above, and write the manifest back.  Preserve\n"
        "all unchanged entries exactly as they are."
    ).format(folder=folder, sources=_format_sources(sources))


def _build_scope_prompt(folder: str, scope_kind: str, sources: list[dict]) -> str:
    """Build a prompt for scope-level roots (global / project / workspace)."""
    return (
        "Update the {scope_kind} memory manifest at ``{folder}``.\n"
        "\n"
        "The {scope_kind} root is at ``{folder}``.  Its ``agents/``\n"
        "directory contains agent sub-directories.\n"
        "\n"
        "The following source paths have changed:\n"
        "{sources}\n"
        "\n"
        "Read the existing ``.memory_sources.md`` manifest at\n"
        "``{folder}``, update the git commit hashes for the changed\n"
        "sources listed above, and write the manifest back.  Preserve\n"
        "all unchanged entries exactly as they are."
    ).format(scope_kind=scope_kind, folder=folder, sources=_format_sources(sources))


# ---------------------------------------------------------------------------
# Per-layer merge functions
# ---------------------------------------------------------------------------


def merge_workspace_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a workspace agent-task manifest."""
    return _do_merge("task", folder, sources, session)


def merge_workspace_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a workspace agent manifest."""
    return _do_merge("agent", folder, sources, session)


def merge_workspace(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a workspace root manifest."""
    return _do_merge("scope", folder, sources, session)


def merge_project_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a project agent-task manifest."""
    return _do_merge("task", folder, sources, session)


def merge_project_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a project agent manifest."""
    return _do_merge("agent", folder, sources, session)


def merge_project(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a project root manifest."""
    return _do_merge("scope", folder, sources, session)


def merge_global_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a global agent-task manifest."""
    return _do_merge("task", folder, sources, session)


def merge_global_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a global agent manifest."""
    return _do_merge("agent", folder, sources, session)


def merge_global(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a global root manifest."""
    return _do_merge("scope", folder, sources, session)


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------


def _do_merge(
    level: str, folder: str, sources: list[dict], session: Any = None
) -> tuple[bool, dict]:
    """Create a memory-manage session, send the prompt, and wait for result.

    Args:
        level: ``"task"``, ``"agent"``, or ``"scope"``.
        folder: Path to the manifest directory.
        sources: List of changed source dicts from ``needs_update``.
        session: Optional caller session for workspace context.

    Returns:
        ``(success, result)`` – on success *result* contains the LLM output;
        on failure a dict with ``"error"``.
    """
    # Create the memory-manage session
    mem_session = _create_memory_session(level, folder, sources, session)
    if mem_session is None:
        return False, {"error": "Could not create memory-manage session"}

    # Build the layer-specific prompt
    if level == "task":
        prompt = _build_task_prompt(folder, sources)
    elif level == "agent":
        prompt = _build_agent_prompt(folder, sources)
    else:
        # scope – determine scope kind from folder path
        scope_kind = _infer_scope(folder, "scope")
        prompt = _build_scope_prompt(folder, scope_kind, sources)

    # Send the prompt and wait for the LLM to process
    call = mem_session.add_user_message(prompt)
    try:
        result = call.get_result(timeout=300)
        return True, {"result": str(result)[:1000]}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": str(exc)}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def memory_merge(
    needs_update: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Process the first item from ``walk_memory``'s ``needs_update`` list.

    Args:
        needs_update: The ``needs_update`` list returned by
            :func:`runtime.memory.tree.walk_memory`.  Each entry has
            ``manifest_path``, ``node_kind``, ``node_key``, ``depth``,
            and ``sources``.
        session: Optional session context for delegation.

    Returns:
        ``(success, result)`` – on success *result* contains the merge
        outcome; on failure a dict with ``"error"``.
    """
    if not needs_update:
        return True, {"message": "No items need updating."}

    # Take the first (deepest) item
    item = needs_update[0]
    folder = item["manifest_path"]
    sources = item["sources"]
    node_kind = item["node_kind"]

    # Determine the scope kind
    scope = _infer_scope(folder, node_kind)

    # Dispatch to the right merge function
    func_name = f"merge_{scope}_{node_kind}"
    func = globals().get(func_name)
    if func is None:
        return False, {"error": f"No merge function for {scope}/{node_kind}"}

    try:
        success, result = func(folder, sources, session=session)
        return success, {
            "merged": True,
            "scope": scope,
            "kind": node_kind,
            "folder": folder,
            "source_count": len(sources),
            "result": result,
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": str(exc)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_scope(folder: str, node_kind: str) -> str:
    """Infer the scope kind from the manifest path and node kind."""
    if node_kind in ("global", "project", "workspace"):
        return node_kind

    folder_lower = folder.lower()

    # Project scope: path contains /projects/
    if "/projects/" in folder_lower or "\\projects\\" in folder_lower:
        return "project"

    # Workspace scope: path contains /workspaces/ or .agentone is nested
    # inside a workspace project directory (not directly under $HOME)
    if "/workspaces/" in folder_lower or "\\workspaces\\" in folder_lower:
        return "workspace"

    if "/.agentone/memory" in folder_lower:
        try:
            p = Path(folder)
            for parent in p.parents:
                if parent.name == ".agentone":
                    grandparent = parent.parent
                    gp_str = str(grandparent)
                    home = str(Path.home())
                    if gp_str != home and gp_str.rstrip("/") != home.rstrip("/"):
                        return "workspace"
                    break
        except Exception:
            pass

    return "global"