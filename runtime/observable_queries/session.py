"""Callback subscriptions to explicit session-scoped observable queries."""
from __future__ import annotations

from django.db.models.fields.reverse_related import ManyToOneRel

from runtime.observable_queries.base import Callback, _subscribe_queryset
from runtime.observable_queries.subscription import ObservableSubscription
from server.models.sessions.session import SessionModel


class ObservableSession:
    """Observable collections belonging to one session."""

    def __init__(self, session: SessionModel):
        if not isinstance(session, SessionModel):
            session = getattr(session, "model", None)
        if not isinstance(session, SessionModel):
            raise TypeError("ObservableSession requires a SessionModel or runtime Session")
        self.session = session

    def get_child_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of direct child sessions."""
        return self._related("child_sessions", callback)

    def get_active_child_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of direct active child sessions."""
        return self._related(
            "child_sessions",
            callback,
            is_active=True,
        )

    def get_messages(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of messages."""
        return self._related("related_messages", callback)

    def get_queries(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of queries."""
        return self._related("related_queries", callback)

    def get_responses(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of responses."""
        return self._related("related_response", callback)

    def get_session_versions(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of session configuration versions."""
        return self._related("related_session_versions", callback)

    def get_task_calls(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of task calls."""
        return self._related("related_agent_task_calls", callback)

    def get_task_runs(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of task runs."""
        return self._related("related_task_runs", callback)

    def get_task_instances(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of task instances."""
        return self._related("related_task_instances", callback)

    def get_templates(self, callback: Callback) -> ObservableSubscription:
        """Observe query-template links for this session."""
        return self._related("query_template_links", callback)

    def get_adhoc_tools(self, callback: Callback) -> ObservableSubscription:
        """Observe ad-hoc tool links for this session."""
        return self._related("adhoc_tool_links", callback)

    def get_terminals(self, callback: Callback) -> ObservableSubscription:
        """Observe terminal sessions associated with this session."""
        return self._related("terminals", callback)

    def get_debug_entries(self, callback: Callback) -> ObservableSubscription:
        """Observe debug log entries for this session."""
        return self._related("debug_log_entries", callback)

    def _related(
        self,
        relation_name: str,
        callback: Callback,
        **filters: object,
    ) -> ObservableSubscription:
        relation = self.session._meta.get_field(relation_name)
        if not isinstance(relation, ManyToOneRel):
            raise TypeError(f"{relation_name!r} is not a reverse foreign-key relation")
        queryset = getattr(self.session, relation_name).filter(**filters)
        model = queryset.model
        foreign_key = relation.field
        return _subscribe_queryset(
            queryset,
            model,
            (model.__name__, f"{model.__name__}.{foreign_key.name}:{self.session.pk}"),
            callback,
            lambda item: (
                item["model"] == model.__name__
                and item.get(foreign_key.attname) == self.session.pk
                and all(item.get(name) == value for name, value in filters.items())
            ),
        )
