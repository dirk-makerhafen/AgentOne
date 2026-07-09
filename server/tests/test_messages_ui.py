from __future__ import annotations
from unittest.mock import MagicMock
from django.test import TestCase
from server.models.message import Message
from server.models.queries.query import Query, QueryStatus
from server.models import SessionModel, SessionVersionModel, AgentModel, AgentVersionModel
from ui.app import UiApp
from ui.main.chat.messages.messages import Messages


class MockChat:
    """Minimal Chat stand-in that provides the parent interface Messages needs."""

    def __init__(self):
        self._instance = MagicMock()
        self._instance.add_css_string = MagicMock()
        self._instance.call_javascript = MagicMock()

    def _add_child(self, child):
        pass


class MessagesTest(TestCase):
    def setUp(self):
        # ── UiApp ──
        self.ui_app = UiApp()
        # Clean up any previous instance reference (UiApp.__init__ sets it)
        if hasattr(self, "_old_instance"):
            pass

        # ── DB models ──
        self.agent = AgentModel.objects.create(name="test_agent")
        self.agent_version = AgentVersionModel.objects.create(
            agent=self.agent, version_number=1
        )
        self.session_model = SessionModel.objects.create(name="test_session")
        self.session_version = SessionVersionModel.objects.create(
            session=self.session_model,
            agent=self.agent,
            pinned_agent_version=self.agent_version,
            version_number=1,
        )
        SessionModel.objects.filter(pk=self.session_model.pk).update(
            latest_session_version=self.session_version,
        )
        self.session_model.refresh_from_db()

        # ── Mock Runtime Session wrapper ──
        self.runtime_session = MagicMock()
        self.runtime_session.model = self.session_model

        # ── Mock Chat parent ──
        self.chat = MockChat()

        # ── Messages view ──
        self.messages = Messages(
            subject=self.runtime_session,
            parent=self.chat,
        )
        # Activate the ObservableListView so _on_subject_updated fires on
        # subsequent append/insert calls (in production this happens in render()).
        self.messages.messages_view.set_visible(True)

    def tearDown(self):
        # Reset UiApp singleton so other tests don't see this instance
        UiApp._instance = None

    def _create_message(self, role: str = "user",
                        session_version=None) -> Message:
        return Message.objects.create(
            role=role,
            session_version=session_version or self.session_version,
        )

    def test_on_message_created_appends_message(self):
        """_on_message_created appends a new Message to the observable list."""
        msg = self._create_message(role="user")
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        pks = [item.pk for item in self.messages.message_list]
        self.assertIn(msg.pk, pks,
                      "Message pk should be in the observable list after append")

    def test_on_message_created_dedup(self):
        """_on_message_created does NOT add the same pk twice."""
        msg = self._create_message(role="user")
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        count_before = len(self.messages.message_list)
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        self.assertEqual(len(self.messages.message_list), count_before,
                         "Duplicate pk should not change list length")

    def test_on_message_created_adds_related_queries(self):
        """If a message already has related Queries, they are appended too."""
        msg = self._create_message(role="user")
        query = Query.objects.create(
            trigger_message=msg,
            session_version=self.session_version,
            status=QueryStatus.ACTIVE,
        )
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        pks = [item.pk for item in self.messages.message_list]
        self.assertIn(msg.pk, pks, "Message should be in list")
        self.assertIn(query.pk, pks,
                      "Related Query should also be in list")

    def test_on_query_created_inserts_after_trigger_message(self):
        """_on_query_created inserts a Query after its trigger_message."""
        msg = self._create_message(role="user",
                                   session_version=self.session_version)
        query = Query.objects.create(
            trigger_message=msg,
            session_version=self.session_version,
            status=QueryStatus.WAITING,
        )
        # First add the trigger message
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        trigger_idx = next(
            i for i, item in enumerate(self.messages.message_list)
            if isinstance(item, Message) and item.pk == msg.pk
        )
        # Now simulate the Query create event
        self.messages._on_query_created(query.pk, "create", {
            "session_id": self.session_model.pk,
            "trigger_message_id": msg.pk,
        })
        q_idx = next(
            i for i, item in enumerate(self.messages.message_list)
            if isinstance(item, Query) and item.pk == query.pk
        )
        self.assertEqual(q_idx, trigger_idx + 1,
                         "Query should be inserted right after trigger_message")

    def test_on_query_created_dedup(self):
        """_on_query_created does NOT insert if the Query is already in the list."""
        msg = self._create_message(role="user")
        query = Query.objects.create(
            trigger_message=msg,
            session_version=self.session_version,
            status=QueryStatus.WAITING,
        )
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        self.messages._on_query_created(query.pk, "create", {
            "session_id": self.session_model.pk,
            "trigger_message_id": msg.pk,
        })
        count_before = len(self.messages.message_list)
        self.messages._on_query_created(query.pk, "create", {
            "session_id": self.session_model.pk,
            "trigger_message_id": msg.pk,
        })
        self.assertEqual(len(self.messages.message_list), count_before,
                         "Duplicate Query pk should not change list length")

    def test_on_query_updated_refreshes_view(self):
        """_on_query_updated calls update() on the matching QueryView."""
        msg = self._create_message(role="user")
        query = Query.objects.create(
            trigger_message=msg,
            session_version=self.session_version,
            status=QueryStatus.WAITING,
        )
        # Add message + query to the list
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        self.messages._on_query_created(query.pk, "create", {
            "session_id": self.session_model.pk,
            "trigger_message_id": msg.pk,
        })
        # Find the wrapper in _wrapped_data
        wrapper = next(
            (
                w for w in self.messages.messages_view._wrapped_data
                if hasattr(w, 'subject') and isinstance(w.subject, Query)
                   and w.subject.pk == query.pk
            ),
            None,
        )
        self.assertIsNotNone(wrapper, "Query wrapper should exist in _wrapped_data")
        wrapper.view.update = MagicMock()
        self.messages._on_query_updated(query.pk, "update", {
            "session_id": self.session_model.pk,
        })
        wrapper.view.update.assert_called_once()

    def test_unwatch_filter_cleans_up_old_subscriptions(self):
        """Calling Messages.__init__ twice cleans up old model_observer subs."""
        obs = self.ui_app.model_observer
        subs_before = len(obs._subscriptions.get("message", []))
        # Re-initialize (simulates closing + reopening a tab)
        messages2 = Messages(
            subject=self.runtime_session,
            parent=self.chat,
        )
        self.assertIsNotNone(messages2)
        subs_after = len(obs._subscriptions.get("message", []))
        self.assertEqual(subs_after, subs_before,
                         "Re-init should not increase subscription count")
