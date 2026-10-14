from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from server.models.sessions.session import SessionModel


class Sessions:
    """Query interface for SessionModel instances.

    Scoping is explicit: ``parent_project`` selects its child sessions;
    ``parent_session`` (runtime ``Session`` or ``SessionModel``) selects
    its children; both *None* means all rows.
    """

    def __init__(
        self,
        parent_project: Any = None,
        parent_session: Any = None,
    ) -> None:
        self.parent_project = parent_project
        self.parent_session = parent_session

    @property
    def project(self) -> Any | None:
        """Return the scope project (explicit or session-unwrapped)."""
        if self.parent_project is not None:
            return self.parent_project
        parent = self.parent_session
        if isinstance(parent, SessionModel):
            return parent.parent_project
        try:
            model = getattr(parent, "model", None)
            if isinstance(model, SessionModel):
                return model.parent_project
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return None

    def all(self) -> QuerySet[SessionModel]:
        """Return sessions in scope (newest first)."""
        qs = SessionModel.objects.all()
        session = self.parent_session
        if session is not None:
            if not isinstance(session, SessionModel):
                try:
                    session = getattr(session, "model", None)
                except Exception:  # pylint: disable=broad-exception-caught
                    session = None
            if isinstance(session, SessionModel):
                return qs.filter(parent_session=session).order_by("-created_at")
            return qs.none()
        project = self.project
        if project is not None:
            qs = qs.filter(parent_project=project)
        return qs.order_by("-created_at")

    def root(self) -> QuerySet[SessionModel]:
        """Return all sessions (unscoped; UI + legacy callers)."""
        #return SessionModel.objects.filter(parent_session__isnull=True)
        return SessionModel.objects.filter()

    def list_sessions(self) -> list:
        """Return sessions in scope as wrapped :class:`Session` objects."""
        from runtime.session.session import Session

        return [
            Session(session_model=model)
            for model in self.all().select_related("latest_session_version")
        ]

    @staticmethod
    def project_of(session: Any) -> Any | None:
        """Return the project a session belongs to, or *None* for global.

        Shared replacement for the ``_session_project`` helpers previously
        copy-pasted across the internal assistant scripts.
        """
        from runtime.project.projects import project_of

        try:
            model = getattr(session, "model", None)
            if model is None:
                return project_of(session)
            return project_of(model)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    # ------------------------------------------------------------------
    # Assistant sessions (choke point for the *_assistant/*s_assistant pairs)
    # ------------------------------------------------------------------

    def assistant_session(
        self,
        name: str,
        *,
        project: Any = None,
        workspace: Any = None,
        caller: Any = None,
        session_type: str = "",
    ) -> Any | None:
        """Get-or-create the singleton assistant session, bound to its scope.

        The session is named ``<assistant>:global`` (project-less) or
        ``<assistant>:<project-path>`` so every caller shares one
        conversation per scope. The scope's project is stamped on
        ``SessionModel.parent_project`` so the assistant's own scoped tools
        resolve the right collection.

        Args:
            name: Internal assistant agent name (e.g. ``skills_assistant``).
            project: Scope project (a ``Project`` row) or *None* for global.
            workspace: Bound workspace row (or *None* to inherit/no-bind).
            caller: Calling runtime ``Session`` — parents the new session
                for auto-await delivery and resolves internal agents.
                Without a caller the agent version is resolved globally.
            session_type: SessionType value (defaults to ``subsession``).

        Returns:
            The runtime ``Session``, or *None* when unresolvable.
        """
        from server.models.agents.agent import AgentModel
        from server.models.enums.session_enums import SessionType

        assistant = (name or "").strip()
        if not assistant:
            return None
        session_name, description = _assistant_session_naming(assistant, project)
        wanted_type = session_type or SessionType.SUBSESSION

        if caller is not None:
            try:
                return caller.spawn_subagent(
                    assistant,
                    name=session_name,
                    description=description,
                    workspace=workspace,
                    project=project,
                    session_type=wanted_type,
                    allow_internal=True,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                return None

        try:
            agent_model = AgentModel.objects.filter(name=assistant).first()
            if agent_model is None or agent_model.latest_agent_version is None:
                return None
            session_version = agent_model.latest_agent_version.get_or_create_session(
                name=session_name,
                description=description,
                workspace=workspace,
                session_type=wanted_type,
            )
            session = session_version.session
            project_pk = getattr(project, "pk", None)
            if project_pk is not None and session.parent_project_id != project_pk:
                session.parent_project = project
                session.save(update_fields=["parent_project_id"])
            from runtime.session.session import Session

            return Session(session_model=session, pinned_session_version=session_version)
        except Exception:  # pylint: disable=broad-exception-caught
            return None


def _assistant_session_naming(assistant: str, project: Any) -> tuple[str, str]:
    """Return the singleton (session name, description) for a scope."""
    key = "global"
    if project is not None:
        try:
            key = (project.path or "").strip() or f"project-{project.pk}"
        except Exception:  # pylint: disable=broad-exception-caught
            key = f"project-{getattr(project, 'pk', '?')}"
    return f"{assistant}:{key}", f"{assistant} session ({key})"

