from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet

from server.models.project import Project


class Projects:
    """Query interface for Project instances.

    Projects are top-level entities: any parent kwarg raises ``TypeError``
    (no sub-projects). There is no scoping — ``all()`` always sees every
    registered project.
    """

    #: Collection domain label.
    DOMAIN = "projects"
    #: Internal assistant pair managing projects (singular, plural).
    ASSISTANT_NAMES = ("project_assistant", "projects_assistant")

    def __init__(self, **kwargs: Any) -> None:
        if kwargs:
            raise TypeError(
                "Projects() takes no parent "
                f"(got {sorted(kwargs)}); projects are top-level entities."
            )

    def all(self) -> QuerySet[Project]:
        """Return all projects, ordered by name."""
        return Project.objects.all().order_by("name")

    @property
    def project(self) -> None:
        """Return the scope project — always *None* (projects are global)."""
        return None

    def root(self) -> QuerySet[Project]:
        """Return all projects (unscoped; UI + legacy callers)."""
        return Project.objects.all()

    def list_projects(self) -> list:
        """Return all projects as wrapped :class:`Project` objects."""
        from runtime.project.project import Project as ProjectScope

        return [ProjectScope(model) for model in self.all()]

    def get_source_dir(self) -> Path:
        """Return the framework home (projects have no single source dir)."""
        from runtime.paths import agentone_home

        return agentone_home()

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    @property
    def assistant_name(self) -> str:
        """Return the collection assistant managing projects."""
        return self.ASSISTANT_NAMES[1]

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton projects-assistant session (global scope)."""
        from runtime.session.sessions import Sessions
        from runtime.workspace.workspaces import Workspaces

        return Sessions().assistant_session(
            name or self.assistant_name,
            project=None,
            workspace=Workspaces.ensure_named(
                "AgentOne system",
                self.get_source_dir(),
                "Master workspace: whole framework home",
            ),
            caller=caller,
        )
