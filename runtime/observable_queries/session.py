"""Callback subscriptions to explicit session-scoped observable queries."""
from __future__ import annotations

from runtime.observable_queries.base import Callback
from runtime.observable_queries.root import ObservableRoot
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
        self._root = ObservableRoot()

    def get_child_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe direct child sessions, newest first."""
        return self._related("child_sessions", callback, order_by=("-created_at",))

    def get_active_child_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe direct active child sessions, newest first."""
        return self._related(
            "child_sessions",
            callback,
            order_by=("-created_at",),
            queryset_filter={"is_active": True},
            predicate_fields={"is_active": True},
        )

    def get_messages(self, callback: Callback) -> ObservableSubscription:
        """Observe messages in chronological order."""
        return self._related("related_messages", callback, order_by=("created_at",))

    def get_queries(self, callback: Callback) -> ObservableSubscription:
        """Observe queries in chronological order."""
        return self._related("related_queries", callback, order_by=("created_at",))

    def get_responses(self, callback: Callback) -> ObservableSubscription:
        """Observe responses in chronological order."""
        return self._related("related_response", callback, order_by=("created_at",))

    def get_session_versions(self, callback: Callback) -> ObservableSubscription:
        """Observe session configuration versions."""
        return self._related("related_session_versions", callback, order_by=("version_number",))

    def get_task_calls(self, callback: Callback) -> ObservableSubscription:
        """Observe task calls in creation order."""
        return self._related("related_agent_task_calls", callback, order_by=("created_at",))

    def get_task_runs(self, callback: Callback) -> ObservableSubscription:
        """Observe task runs in creation order."""
        return self._related("related_task_runs", callback, order_by=("created_at",))

    def get_task_instances(self, callback: Callback) -> ObservableSubscription:
        """Observe task instances in creation order."""
        return self._related("related_task_instances", callback, order_by=("created_at",))

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
        order_by: tuple[str, ...] = (),
        queryset_filter: dict | None = None,
        predicate_fields: dict | None = None,
    ) -> ObservableSubscription:
        relation = self.session._meta.get_field(relation_name)
        child_model = relation.related_model
        if child_model is None:
            raise TypeError(f"{relation_name} has no related model")
        queryset = getattr(self.session, relation_name).all()
        if queryset_filter:
            queryset = queryset.filter(**queryset_filter)
        if order_by:
            queryset = queryset.order_by(*order_by)
        return self._root._observe_related(
            self.session,
            relation_name,
            child_model,
            callback,
            predicate_fields=predicate_fields,
            queryset=queryset,
        )
