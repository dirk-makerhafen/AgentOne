"""Shared scope + assistant wiring for runtime entity wrappers.

Every runtime *plural* collection (``Agents``, ``Skills``, ...) and the
matching *singular* wrapper expose the same three things: the collection's
assistant name, the scope project, and a get-or-create accessor for the
singleton assistant session. :class:`AssistantScopeMixin` centralizes that
wiring, so each domain class only declares its ``ASSISTANT_NAMES`` (or
``ASSISTANT``) plus its domain-specific ``get_source_dir`` and
``get_assistant_workspace``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class AssistantScopeMixin:
    """Scope + assistant-session plumbing shared by runtime wrappers.

    Subclasses provide:

    * ``ASSISTANT_NAMES`` — ``(singular, plural)`` pair for plural
      collections, or ``ASSISTANT`` — one name for singular wrappers;
    * ``get_assistant_workspace()`` — the row the assistant sessions bind to;
    * ``get_source_dir()`` — the manifest/source directory for the scope.

    The mixin supplies ``assistant_name``, ``project``,
    ``assistant_scope_label`` and ``get_assistant_session`` on top of those.
    Singular wrappers override :meth:`assistant_scope_label` to name their
    item (e.g. ``agent_assistant - Alpha``).
    """

    #: ``(singular, plural)`` assistant pair for plural collections.
    ASSISTANT_NAMES: tuple[str, str] = ("", "")
    #: Single assistant name for singular wrappers.
    ASSISTANT: str = ""
    #: Collection domain label (used by plural collections).
    DOMAIN: str = ""

    @property
    def assistant_name(self) -> str:
        """Return the collection assistant managing this scope."""
        if self.ASSISTANT_NAMES[1]:
            return self.ASSISTANT_NAMES[1]
        return self.ASSISTANT

    @property
    def project(self) -> Any | None:
        """Return the scope project (explicit, else unwrapped from an owner)."""
        explicit = getattr(self, "parent_project", None)
        if explicit is not None:
            return explicit
        for owner in (
            getattr(self, "parent_workspace", None),
            getattr(self, "parent_agent", None),
            getattr(self, "parent_skill", None),
        ):
            if owner is None:
                continue
            try:
                project = getattr(owner, "parent_project", None)
            except Exception:  # pylint: disable=broad-exception-caught
                project = None
            if project is not None:
                return project
        return None

    def assistant_scope_label(self) -> str:
        """Return the human label naming this scope in assistant sessions.

        Plural collections label themselves by their most specific owner
        (``agent Alpha`` / ``workspace Foo`` / ``skill Bar``), else the
        project name, else ``global``. Singular wrappers override this to
        return the item's own name.
        """
        for attr, kind in (
            ("parent_workspace", "workspace"),
            ("parent_agent", "agent"),
            ("parent_skill", "skill"),
        ):
            owner = getattr(self, attr, None)
            if owner is None:
                continue
            name = self._labelled_name(owner)
            if name:
                return f"{kind} {name}"
        project = self.project
        if project is not None:
            name = self._labelled_name(project)
            if name:
                return name
        return "global"

    @staticmethod
    def _labelled_name(row: Any) -> str:
        """Return a non-empty ``name`` or ``path`` for *row* (else ``""``)."""
        for attr in ("name", "path"):
            try:
                value = (getattr(row, attr, "") or "").strip()
            except Exception:  # pylint: disable=broad-exception-caught
                value = ""
            if value:
                return value
        return ""

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton assistant session for this scope.

        *name* defaults to the collection assistant; pass the singular name
        to talk about ONE item (named inside the task text).
        """
        from runtime.session.sessions import Sessions

        return Sessions().assistant_session(
            name or self.assistant_name,
            project=self.project,
            workspace=self.get_assistant_workspace(),
            caller=caller,
            scope_label=self.assistant_scope_label(),
        )

    def get_source_dir(self) -> Path:  # pragma: no cover - overridden per domain
        """Return the source directory anchoring this scope (no I/O)."""
        raise NotImplementedError

    def get_assistant_workspace(self) -> Any:  # pragma: no cover - overridden per domain
        """Return the row binding this scope's assistant sessions."""
        raise NotImplementedError
