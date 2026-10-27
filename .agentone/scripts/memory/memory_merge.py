"""Update memory manifests for changed sources.

When ``walk_memory`` reports items in ``needs_update``, this module provides
a way to selectively update a single manifest by re-computing git hashes for
the changed source paths.

Different layers (workspace root, agent, task) get different prompts when
delegating to the project assistant, because the semantic meaning of
``agents/``, ``tasks/``, and ``sessions/`` directories differs across
scope levels.
"""

from __future__ import annotations

from pathlib import Path

from runtime.memory.tree import mempaths


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


def _build_prompt(scope: str, kind: str, folder: str, sources: list[dict]) -> str:
    """Build a layer-specific prompt for the project assistant."""
    sources_text = _format_sources(sources)

    if kind == "task":
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
        )

    if kind == "agent":
        return (
            "Update the memory manifest at ``{folder}``.\n"
            "\n"
            "This is an agent directory inside a {scope} scope.  The ``tasks/``\n"
            "directory contains task sub-directories, each with session reports.\n"
            "\n"
            "The following source paths have changed:\n"
            "{sources}\n"
            "\n"
            "Read the existing ``.memory_sources.md`` manifest at\n"
            "``{folder}``, update the git commit hashes for the changed\n"
            "sources listed above, and write the manifest back.  Preserve\n"
            "all unchanged entries exactly as they are."
        )

    # workspace / project / global – similar structure
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
    )


# ---------------------------------------------------------------------------
# Per-layer merge functions
# ---------------------------------------------------------------------------


def merge_workspace_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a workspace agent-task manifest."""
    return _do_merge("workspace", "task", folder, sources)


def merge_workspace_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a workspace agent manifest."""
    return _do_merge("workspace", "agent", folder, sources)


def merge_workspace(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a workspace root manifest."""
    return _do_merge("workspace", "workspace", folder, sources)


def merge_project_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a project agent-task manifest."""
    return _do_merge("project", "task", folder, sources)


def merge_project_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a project agent manifest."""
    return _do_merge("project", "agent", folder, sources)


def merge_project(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a project root manifest."""
    return _do_merge("project", "project", folder, sources)


def merge_global_agent_task(
    folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Merge changes into a global agent-task manifest."""
    return _do_merge("global", "task", folder, sources)


def merge_global_agent(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a global agent manifest."""
    return _do_merge("global", "agent", folder, sources)


def merge_global(folder: str, sources: list[dict], *, session=None):
    """Merge changes into a global root manifest."""
    return _do_merge("global", "global", folder, sources)


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------


def _do_merge(
    scope: str, kind: str, folder: str, sources: list[dict], *, session=None
) -> tuple[bool, dict]:
    """Update the manifest at *folder* for the changed *sources*.

    Strategy:
    1. Read the existing ``.memory_sources.md`` manifest.
    2. For each changed source, re-read its directory and compute the new
       git commit hash.
    3. Update the manifest entries with the new hashes.
    4. Write the updated manifest back.
    """
    from runtime.memory import memgit, memsources

    manifest_path = Path(folder) / mempaths.SOURCES_FILENAME
    if not manifest_path.exists():
        return False, {"error": f"Manifest not found: {manifest_path}"}

    # Read existing manifest
    try:
        manifest_data = memsources.read_sources(manifest_path)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": f"Failed to read manifest: {exc}"}

    # Compute new hashes for changed sources
    updated = 0
    for src in sources:
        src_path = src.get("path", "")
        if not src_path:
            continue

        full_path = Path(folder) / src_path
        if not full_path.is_dir():
            # Source directory doesn't exist; keep the existing hash
            continue

        repo = memgit.repo_for(full_path)
        if repo is None:
            continue

        new_hash = memgit.current_commit(repo, full_path)
        if not new_hash:
            continue

        # Update the manifest entry
        for entry in manifest_data.get("sources", []):
            if entry.get("path") == src_path:
                entry["last_processed_hash"] = new_hash
                updated += 1
                break

    if updated == 0:
        return True, {
            "scope": scope,
            "kind": kind,
            "folder": folder,
            "source_count": len(sources),
            "message": "No hashes needed updating.",
        }

    # Write updated manifest
    try:
        memsources.write_sources(manifest_path, manifest_data)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": f"Failed to write manifest: {exc}"}

    return True, {
        "scope": scope,
        "kind": kind,
        "folder": folder,
        "source_count": len(sources),
        "updated": updated,
        "message": f"Updated {updated} source hash(es) in manifest.",
    }


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
        session: Optional session context (unused, kept for API compat).

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

    # For agent/task nodes, inspect the path
    folder_lower = folder.lower()
    if "/projects/" in folder_lower or "\\projects\\" in folder_lower:
        return "project"
    if "/workspaces/" in folder_lower or "\\workspaces\\" in folder_lower:
        return "workspace"
    return "global"