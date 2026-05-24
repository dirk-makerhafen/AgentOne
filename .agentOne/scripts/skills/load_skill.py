"""
Load a skill's markdown content by name.

Uses the session's allowed skills to look up a SkillModelVersion, reads
the versioned ``skill.md`` from ``~/.agentone/runtime/<pk>/``, parses
YAML frontmatter, and returns the metadata + body to the agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter

if TYPE_CHECKING:
    from runtime.session.session import Session


def load_skill(session: Session, skill_name: str) -> tuple[bool, dict]:
    """
    Load a skill's content by name (frontmatter metadata + markdown body).

    Args:
        session: The calling agent's session (bound automatically).
        skill_name: The name of the skill to load (e.g. ``"document-scanner"``).

    Returns:
        A tuple ``(success, result_dict)``.

    On success, *result_dict* contains:

    .. code-block:: python

        {
            "status": "success",
            "name": "document-scanner",
            "description": "...",
            "version": 1,
            "metadata": {"name": "...", "description": "..."},
            "body": "# Skill content...\\n"
        }

    On failure, *result_dict* contains ``status`` and ``message``.
    """
    skill_version = session.get_skill(skill_name)
    if skill_version is None:
        return (
            False,
            {
                "status": "error",
                "message": f"Skill '{skill_name}' not found or not allowed",
            },
        )

    skill_path = skill_version.path
    if not skill_path:
        return (
            False,
            {
                "status": "error",
                "message": f"Skill '{skill_name}' has no file path on disk",
            },
        )

    md_path = Path(skill_path)
    if not md_path.is_file():
        return (
            False,
            {
                "status": "error",
                "message": f"Skill file not found on disk: {skill_path}",
            },
        )

    raw = md_path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(raw)
    except Exception as exc:
        return (
            False,
            {
                "status": "error",
                "message": f"Failed to parse skill frontmatter: {exc}",
            },
        )

    return (
        True,
        {
            "status": "success",
            "name": skill_version.skill.name if skill_version.skill else skill_name,
            "description": skill_version.description,
            "version": skill_version.version_number,
            "metadata": post.metadata,
            "body": post.content,
        },
    )


if __name__ == "__main__":
    import argparse
    import json
    import os
    import sys

    sys.path.insert(
        0,
        os.path.join(os.path.dirname(__file__), "..", ".."),
    )

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()

    from server.models.sessions.session import SessionModel
    from runtime.session.session import Session as RuntimeSession

    parser = argparse.ArgumentParser(description="Load a skill by name")
    parser.add_argument("skill_name", type=str, help="Name of the skill to load")
    parser.add_argument(
        "--session-pk",
        type=int,
        default=None,
        help="Session PK to use (requires running server)",
    )
    args = parser.parse_args()

    if args.session_pk:
        session_model = SessionModel.objects.get(pk=args.session_pk)
        session = RuntimeSession(session_model=session_model)
        success, result = load_skill(session, args.skill_name)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if success else 1)
    else:
        print(
            "CLI mode requires --session-pk to point at an active session.",
            file=sys.stderr,
        )
        sys.exit(1)
