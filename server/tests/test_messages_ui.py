from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.test import TestCase
from server.models.enums.message_enums import MessageRole
from server.models.enums.session_enums import SessionType
from server.models.message import Message, MessagePartType, MessageContentType
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

    def _create_message(self, role: str = MessageRole.USER,
                        session_version=None) -> Message:
        sv = session_version or self.session_version
        return Message.objects.create(
            role=role,
            session=sv.session,
            session_version=sv,
        )

    def test_on_message_created_appends_message(self):
        """_on_message_created appends a new Message to the observable list."""
        msg = self._create_message(role=MessageRole.USER)
        self.messages._on_message_created(msg.pk, "create", {
            "session_id": self.session_model.pk,
        })
        pks = [item.pk for item in self.messages.message_list]
        self.assertIn(msg.pk, pks,
                      "Message pk should be in the observable list after append")

    def test_on_message_created_dedup(self):
        """_on_message_created does NOT add the same pk twice."""
        msg = self._create_message(role=MessageRole.USER)
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
        msg = self._create_message(role=MessageRole.USER)
        sv = self.session_version
        query = Query.objects.create(
            trigger_message=msg,
            session = sv.session,
            session_version=sv,
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
        msg = self._create_message(role=MessageRole.USER, session_version=self.session_version)
        sv = self.session_version
        query = Query.objects.create(
            trigger_message=msg,
            session = sv.session,
            session_version=sv,
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
        msg = self._create_message(role=MessageRole.USER)
        sv = self.session_version
        query = Query.objects.create(
            trigger_message=msg,
            session = sv.session,
            session_version=sv,
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
        msg = self._create_message(role=MessageRole.USER)
        sv = self.session_version
        query = Query.objects.create(
            trigger_message=msg,
            session = sv.session,
            session_version=sv,
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

    def test_redis_event_reaches_message_list(self):
        """End-to-end over fakeredis: notify → queue → router → list insert."""
        import json

        import fakeredis

        from runtime import observables
        from ui.consumer import process_queue_messages
        from ui.lib.pyHtmlGui.pyhtmlgui.lib.weakFunctionReferences import (
            WeakFunctionReferences,
        )

        fake = fakeredis.FakeStrictRedis(decode_responses=True)
        instance = SimpleNamespace(
            instance_key="messages-test",
            _function_references=WeakFunctionReferences(),
            observed_views={},
            add_css_string=lambda *a, **k: None,
            call_javascript=lambda *a, **k: None,
        )
        chat = MockChat()
        chat._instance = instance
        with patch.object(observables, "get_redis", return_value=fake):
            messages2 = Messages(subject=self.runtime_session, parent=chat)
            self.assertEqual(
                fake.llen("agentone:uiq:messages-test"), 0, "queue starts empty"
            )
            msg = self._create_message(role=MessageRole.USER)
            msg.notify_observers("create")
            queued = fake.lrange("agentone:uiq:messages-test", 0, -1)
            self.assertEqual(len(queued), 1, "worker write reached the UI queue")
            process_queue_messages(instance, [json.loads(queued[0])])
            self.assertIn(
                msg.pk,
                [item.pk for item in messages2.message_list],
                "dispatched event inserted the message",
            )

    def _fork_wrapper(self, msg):
        """Append *msg* to the list and return its MessageView wrapper."""
        self.messages.message_list.append(msg)
        return next(
            w for w in self.messages.messages_view._wrapped_data
            if isinstance(w.subject, Message) and w.subject.pk == msg.pk
        )

    def test_fork_creates_child_session_anchored_at_message(self):
        """MessageView.fork branches a new child session from the message."""
        msg = self._create_message(role=MessageRole.USER)
        msg.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content="Please continue from here.",
        )
        wrapper = self._fork_wrapper(msg)

        wrapper.fork(msg.pk)

        child = SessionModel.objects.filter(parent_session=self.session_model).first()
        self.assertIsNotNone(child, "Fork should create a child session")
        self.assertEqual(child.session_type, SessionType.SESSION,
                         "A UI fork branch is a permanent user session")
        child_version = child.latest_session_version
        self.assertEqual(child_version.parent_session_version, self.session_version,
                         "Child version should link to the forked-from version")
        anchor = Message.objects.filter(
            session_version__session=child,
            prev_message=msg,
        ).first()
        self.assertIsNotNone(anchor, "Anchor message should point at the fork point")
        self.assertTrue(anchor.hide_from_context,
                        "Anchor should be hidden from LLM context")
        self.assertTrue(anchor.parts.filter(content_type=MessageContentType.TEXT).exists(),
                        "Anchor should carry a body for the UI chain")

    def test_fork_chain_continues_from_anchor(self):
        """After a fork, a new user message chains to the anchor."""
        msg = self._create_message(role=MessageRole.USER)
        wrapper = self._fork_wrapper(msg)
        wrapper.fork(msg.pk)

        child = SessionModel.objects.get(parent_session=self.session_model)
        child_version = child.latest_session_version
        anchor = Message.objects.get(
            session_version__session=child,
            prev_message=msg,
        )
        next_msg = Message.objects.create(
            role=MessageRole.USER,
            session=child_version.session,
            session_version=child_version,
            prev_message=anchor,
        )
        # Walk the chain backwards from the new tail: next_msg -> anchor -> msg
        chain = []
        current = next_msg
        while current is not None and len(chain) < 10:
            chain.append(current.pk)
            current = current.prev_message
        self.assertEqual(chain, [next_msg.pk, anchor.pk, msg.pk],
                         "Branch chain should walk through the fork point")

    def test_parent_tail_survives_fork_children(self):
        """Forking must not hide the parent session's real tail in the UI.

        A fork anchors its first message in the *child* session to the parent
        message via ``prev_message``. That cross-session link shows up in the
        parent message's ``next_messages`` reverse relation, so a naive
        ``filter(next_messages=None)`` tail lookup no longer sees the
        parent's last message — the parent conversation then renders empty
        even though the sidebar still counts its messages.  The tail lookup
        must be scoped to the same session.
        """
        from runtime.session.session import Session as RuntimeSession

        chain = []
        prev = None
        for _ in range(3):
            msg = Message.objects.create(
                role=MessageRole.USER,
                session=self.session_model,
                session_version=self.session_version,
                prev_message=prev,
            )
            chain.append(msg)
            prev = msg

        # Fork from the last message twice, like the reported bug.
        last = chain[-1]
        for _ in range(2):
            wrapper = self._fork_wrapper(last)
            wrapper.fork(last.pk)

        parent_session = RuntimeSession(session_model=self.session_model)

        old = Message.objects.filter(
            session_version__session=self.session_model,
            next_messages=None,
        ).last()
        self.assertIsNone(
            old,
            "Naive next_messages=None lookup is blinded by cross-session fork anchors",
        )
        self.assertEqual(
            parent_session.get_last_message().pk, last.pk,
            "get_last_message must return the parent's own chain tail",
        )

        messages = Messages(subject=parent_session, parent=self.chat)
        messages.messages_view.set_visible(True)
        loaded = [
            item for item in messages.message_list
            if isinstance(item, Message)
        ]
        self.assertEqual(
            [m.pk for m in loaded], [m.pk for m in chain],
            "Parent UI must render its own chain after forks",
        )
