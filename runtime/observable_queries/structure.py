"""Observable project / workspace / provider collections."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
    root_key,
)


class ProjectObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.project import Project

        return Project

    def root(self) -> ObservableList:
        model = self._model()
        return self._list(model.objects.order_by("name"), root_key(model))

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))


class WorkspaceObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.workspace import WorkspaceModel

        return WorkspaceModel

    def root(self) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project__isnull=True).order_by("name"),
            "WorkspaceModel",
        )

    def by_project(self, project_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id).order_by("name"),
            relation_key(model, "parent_project", project_id),
        )


class ProviderObservables(ObservableBase):
    def root(self) -> ObservableList:
        from server.models.providers.api_provider import ApiProvider

        return self._list(ApiProvider.objects.order_by("name"), root_key(ApiProvider))


class AiModelObservables(ObservableBase):
    def by_provider(self, provider_id: int) -> ObservableList:
        from server.models.providers.ai_model import AiModel

        return self._list(
            AiModel.objects.filter(api_provider_id=provider_id).order_by("name"),
            relation_key(AiModel, "api_provider", provider_id),
        )


class TerminalObservables(ObservableBase):
    def by_session(self, session_id: int) -> ObservableList:
        from server.models.terminal import TerminalSession

        return self._list(
            TerminalSession.objects.filter(session_id=session_id).order_by("created_at"),
            relation_key(TerminalSession, "session", session_id),
        )
