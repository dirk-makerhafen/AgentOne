from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.project import Project as ProjectModel


class Project:
    """Runtime wrapper around a Project model instance."""

    #: Singular internal assistant managing ONE project.
    ASSISTANT = "project_assistant"

    def __init__(self, project_model: ProjectModel) -> None:
        self.model = project_model

    @property
    def pk(self) -> Any:
        """Return the project primary key."""
        return self.model.pk

    @property
    def name(self) -> str:
        """Return the project's name."""
        return self.model.name

    @property
    def description(self) -> str:
        """Return the project's description."""
        return self.model.description or ""

    @property
    def path(self) -> str:
        """Return the project's filesystem path."""
        return self.model.path or ""

    @property
    def path_exists(self) -> bool:
        """Return whether the project's path exists on disk."""
        try:
            return Path(self.path).is_dir() if self.path else False
        except OSError:
            return False

    def get_source_dir(self) -> Path:
        """Return the project's manifest directory (stored, else legacy)."""
        from runtime.paths import model_manifest_dir

        return model_manifest_dir(self.model, "project")

    # ------------------------------------------------------------------
    # Child collections
    # ------------------------------------------------------------------

    def get_cronjobs_runtime(self) -> Any:
        """Return the cron jobs owned by this project."""
        from runtime.cron.crons import Cronjobs

        return Cronjobs(parent_project=self.model)

    def get_skills_runtime(self) -> Any:
        """Return the skills visible in this project (global + own)."""
        from runtime.skill.skills import Skills

        return Skills(parent_project=self.model)

    def get_agents_runtime(self) -> Any:
        """Return the agents visible in this project (global + own)."""
        from runtime.agents.agents import Agents

        return Agents(parent_project=self.model)

    def counts(self) -> dict[str, int]:
        """Count the records owned by this project (strict, best effort).

        Unlike the union ``all()`` scopes (global + project), counts only
        include rows owned by the project itself.
        """
        from server.models.agents.agent import AgentModel
        from server.models.cron import Cronjob
        from server.models.sessions.session import SessionModel
        from server.models.skills.skill import SkillModel
        from server.models.workspace import WorkspaceModel
        from server.models.workitems.work_item import WorkItem

        counts: dict[str, int] = {}
        for key, counter in (
            ("agents", lambda: AgentModel.objects.filter(parent_project=self.model).count()),
            ("cronjobs", lambda: Cronjob.objects.filter(parent_project=self.model).count()),
            ("skills", lambda: SkillModel.objects.filter(parent_project=self.model).count()),
            ("workitems", lambda: WorkItem.objects.filter(project=self.model).count()),
            ("sessions", lambda: SessionModel.objects.filter(parent_project=self.model).count()),
            ("workspaces", lambda: WorkspaceModel.objects.filter(parent_project=self.model).count()),
        ):
            try:
                counts[key] = counter()
            except Exception:  # pylint: disable=broad-exception-caught
                counts[key] = 0
        return counts

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this project's assistant sessions.

        The project root workspace. Shared by ``get_assistant_session``
        and UI panels so both bind the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        return Workspaces.for_project(self.model)

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton ``project_assistant`` session for this project.

        Bound to the project root workspace (a superset of the manifest
        dir, so file operations work across the whole project).
        """
        from runtime.session.sessions import Sessions

        return Sessions().assistant_session(
            name or self.ASSISTANT,
            project=self.model,
            workspace=self.get_assistant_workspace(),
            caller=caller,
        )
