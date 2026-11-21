"""Load a skill's markdown content by name.

The implementation lives in ``runtime.skill.load_content`` so this tool and
``admin_tool(scope="skills", action="load")`` return the same payload.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.session.session import Session


def load_skill(_session: "Session", skill_name: str) -> tuple[bool, dict[str, Any]]:
    """Load a skill's content by name (frontmatter metadata + markdown body).

    The skill must be assigned to the calling agent; it is resolved through
    the session's allowed skills and read from the versioned runtime copy of
    ``skill.md``, not the editable manifest.

    Args:
        skill_name: Name of the skill to load (e.g. ``"memory-tick-cycle"``).

    Returns:
        A tuple ``(success, result_dict)``. On success *result_dict* contains
        ``status``, ``name``, ``description``, ``version``, ``metadata`` and
        ``body``; on failure it contains ``status`` and ``message``.
    """
    from runtime.skill.load_content import load_skill_content

    return load_skill_content(_session, skill_name)


if __name__ == "__main__":
    import argparse
    import json
    import os
    import sys

    sys.path.insert(
        0,
        os.path.join(os.path.dirname(__file__), "..", "..", ".."),
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
        _session = RuntimeSession(session_model=session_model)
        success, result = load_skill(_session, args.skill_name)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if success else 1)
    else:
        print(
            "CLI mode requires --session-pk to point at an active session.",
            file=sys.stderr,
        )
        sys.exit(1)
