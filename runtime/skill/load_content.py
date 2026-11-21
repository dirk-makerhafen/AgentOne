"""Read a skill's versioned markdown content for a session.

Shared by the global ``load_skill`` tool and ``admin_tool(scope="skills",
action="load")`` so both resolve skills through the session's allowed skills
and return the same frontmatter + body payload.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter


def load_skill_content(session: Any, skill_name: str) -> tuple[bool, dict[str, Any]]:
    """Return one allowed skill's versioned ``skill.md`` metadata and body.

    Resolution goes through ``session.get_skill`` (the session's allowed
    skills), and the file is read from the version's extracted runtime path —
    never from the editable manifest tree.

    Args:
        session: The calling session (used to resolve allowed skills).
        skill_name: Skill name, e.g. ``"memory-tick-cycle"``.

    Returns:
        ``(success, result)``. On success *result* contains ``status``,
        ``name``, ``description``, ``version``, ``metadata`` and ``body``;
        on failure it contains ``status`` and ``message``.
    """
    name = str(skill_name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A skill name is required."}
    try:
        version = session.get_skill(name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": f"Could not resolve skill '{name}': {exc}"}
    if version is None:
        return False, {"status": "error", "message": f"Skill '{name}' not found or not allowed"}

    path = getattr(version, "path", "") or ""
    if not path:
        return False, {"status": "error", "message": f"Skill '{name}' has no file path on disk"}
    md_path = Path(path)
    if not md_path.is_file():
        return False, {"status": "error", "message": f"Skill file not found on disk: {path}"}

    try:
        post = frontmatter.loads(md_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": f"Failed to parse skill frontmatter: {exc}"}

    skill = getattr(version, "skill", None)
    return True, {
        "status": "success",
        "name": getattr(skill, "name", None) or name,
        "description": getattr(version, "description", "") or "",
        "version": getattr(version, "version_number", 0),
        "metadata": post.metadata,
        "body": post.content,
    }
