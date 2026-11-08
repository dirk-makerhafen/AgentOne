"""Callback subscriptions to explicit root-level observable collections."""
from __future__ import annotations

from typing import Any

from django.db.models import Model, QuerySet

from runtime.observable_queries.base import (
    Callback,
    _filtered_predicate,
    _model_key,
    _model_name,
    _model_predicate,
    _subscribe_queryset,
)
from runtime.observable_queries.subscription import ObservableSubscription
from server.models.base_model import ObservableMixin


class ObservableRoot:
    """Named subscriptions for explicitly supported root collections."""

    def _observe_related(
        self,
        parent: Model,
        relation_name: str,
        model: type[Model] | None,
        callback: Callback,
        *,
        predicate_fields: dict[str, Any] | None = None,
        queryset: QuerySet | None = None,
    ) -> ObservableSubscription:
        """Internal relation subscription with optional named membership rules."""
        from django.core.exceptions import FieldDoesNotExist
        from django.db.models.fields.reverse_related import ManyToOneRel

        try:
            relation = parent._meta.get_field(relation_name)
        except FieldDoesNotExist as exc:
            raise ValueError(
                f"{type(parent)._meta.model.__name__} has no relation {relation_name!r}"
            ) from exc
        if not isinstance(relation, ManyToOneRel) or relation.related_model is None:
            raise TypeError(f"{relation_name!r} is not a reverse foreign-key relation")

        model = model if model is not None else relation.related_model
        if model is None:
            raise TypeError(f"{relation_name!r} has no related model")
        if not issubclass(model, ObservableMixin):
            raise TypeError(f"{model._meta.model_name} does not publish observable events")
        foreign_key = relation.field
        if queryset is None:
            queryset = getattr(parent, relation_name).all()
        if queryset is None:
            raise TypeError(f"{relation_name!r} did not provide a queryset")
        relation_key = f"{_model_name(model)}.{foreign_key.name}:{parent.pk}"
        conditions = {
            foreign_key.attname: parent.pk,
            **(predicate_fields or {}),
        }
        predicate = _filtered_predicate(
            model,
            lambda item: True,
            **conditions,
        )
        return _subscribe_queryset(
            queryset,
            model,
            (_model_key(model), relation_key),
            callback,
            predicate,
        )

    def get_projects(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of projects."""
        from server.models.project import Project

        return self._observe(Project, Project.objects.all(), callback)

    def get_agents(self, callback: Callback) -> ObservableSubscription:
        """Observe active, unparented global agents."""
        from server.models.agents.agent import AgentModel

        queryset = AgentModel.objects.filter(
            parent_project__isnull=True,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
            is_archived=False,
        )
        predicate = _filtered_predicate(
            AgentModel,
            lambda item: True,
            parent_project_id=None,
            parent_agent_id=None,
            parent_skill_id=None,
            is_archived=False,
        )
        return self._observe(AgentModel, queryset, callback, predicate)

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active, unparented global skills."""
        from server.models.skills.skill import SkillModel

        queryset = SkillModel.objects.filter(
            parent_project__isnull=True,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
            is_archived=False,
        )
        predicate = _filtered_predicate(
            SkillModel,
            lambda item: True,
            parent_project_id=None,
            parent_agent_id=None,
            parent_skill_id=None,
            is_archived=False,
        )
        return self._observe(SkillModel, queryset, callback, predicate)

    def _observe(
        self,
        model: type[Model],
        queryset: QuerySet,
        callback: Callback,
        predicate: Any = None,
    ) -> ObservableSubscription:
        return _subscribe_queryset(
            queryset,
            model,
            (_model_key(model),),
            callback,
            predicate or _model_predicate(model),
        )
