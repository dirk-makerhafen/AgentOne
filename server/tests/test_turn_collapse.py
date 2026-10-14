from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock

import jinja2
from django.test import TestCase

from server.models import AgentModel, AgentVersionModel, SessionModel, SessionVersionModel
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
from ui.app import UiApp
from ui.main.chat.messages.assistant_message import AssistantMessageView
from ui.main.chat.messages.messages import Messages
from ui.main.chat.messages.query import QueryView


class MockChat:
    """Minimal Chat stand-in that provides the parent interface Messages needs."""

    def __init__(self):
        self._instance = MagicMock()
        self._instance.add_css_string = MagicMock()
        self._instance.call_javascript = MagicMock()

    def _add_child(self, child):
        pass


class TurnCollapseTest(TestCase):
    def setUp(self):
        self.ui_app = UiApp()
        self.agent = AgentModel.objects.create(name="test_agent")
        self.agent_version = AgentVersionModel.objects.create(
            agent=self.agent, version_number=1
        )
        AgentModel.objects.filter(pk=self.agent.pk).update(
            latest_agent_version=self.agent_version,
        )
        self.agent.refresh_from_db()
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
        self.runtime_session = MagicMock()
        self.runtime_session.model = self.session_model
        self.chat = MockChat()
        self.messages = Messages(
            subject=self.runtime_session,
            parent=self.chat,
        )
        self.messages.messages_view.set_visible(True)

    def tearDown(self):
        UiApp._instance = None

    # ── builders ──
    def _msg(self, role=MessageRole.USER, response=None):
        return Message.objects.create(
            role=role,
            session=self.session_version.session,
            session_version=self.session_version,
            response=response,
        )

    def _query(self, trigger, status=QueryStatus.SUCCESS):
        return Query.objects.create(
            trigger_message=trigger,
            session=self.session_version.session,
            session_version=self.session_version,
            status=status,
        )

    def _resp(self, query, status=ResponseStatus.SUCCESS, total=3.0):
        return Response.objects.create(
            query=query,
            session=self.session_version.session,
            session_version=self.session_version,
            status=status,
            total_time=total,
            completion_tokens=50,
        )

    def _feed_message(self, msg):
        self.messages._on_message_created(msg.pk, "create", {})

    def _feed_query(self, query):
        self.messages._on_query_created(query.pk, "create", {
            "trigger_message_id": query.trigger_message_id,
        })

    def _turn(self, trigger, query_status=QueryStatus.SUCCESS,
              resp_status=ResponseStatus.SUCCESS):
        """Append one full turn (query + assistant) after *trigger*."""
        query = self._query(trigger, status=query_status)
        self._feed_query(query)
        resp = self._resp(query, status=resp_status)
        assistant = self._msg(role=MessageRole.ASSISTANT, response=resp)
        self._feed_message(assistant)
        return query, resp, assistant

    def _turns(self, first_trigger, count):
        """Append *count* chained turns, returning the list."""
        turns = []
        trigger = first_trigger
        for _ in range(count):
            turn = self._turn(trigger)
            turns.append(turn)
            trigger = turn[2]
        return turns

    def _wrapper(self, pk, model):
        for wrapper in self.messages.messages_view._wrapped_data:
            subj = getattr(wrapper, "subject", None)
            if isinstance(subj, model) and subj.pk == pk:
                return wrapper
        return None

    def _assistant_view(self, pk):
        wrapper = self._wrapper(pk, Message)
        return wrapper.view if wrapper is not None else None

    def _query_view(self, pk):
        wrapper = self._wrapper(pk, Query)
        if wrapper is None:
            return None, None
        return wrapper.view, wrapper

    # ── behavior ──
    def test_older_turns_hide_first_visible_carries_count(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        turns = self._turns(user, 4)

        views = [self._assistant_view(a.pk) for _, _, a in turns]
        self.assertTrue(all(views))
        # tail_turns=2 → first two turns hidden, rest visible.
        self.assertTrue(views[0].turn_collapsed)
        self.assertTrue(views[1].turn_collapsed)
        self.assertFalse(views[2].turn_collapsed)
        self.assertFalse(views[3].turn_collapsed)
        # The first visible turn carries the single summary line.
        self.assertEqual(views[2].hidden_count, 2)
        self.assertEqual(views[3].hidden_count, 0)
        self.assertFalse(views[2].block_pinned)
        # Hidden rows (assistant + query) get display:none.
        self.assertIn("display:none", self._wrapper(turns[0][2].pk, Message).DOM_ELEMENT_EXTRAS)
        self.assertIn("display:none", self._wrapper(turns[0][0].pk, Query).DOM_ELEMENT_EXTRAS)
        self.assertIn("display:flex", self._wrapper(turns[2][2].pk, Message).DOM_ELEMENT_EXTRAS)
        # Collapsed turns hide their query rows; tail queries stay visible.
        qview0, _ = self._query_view(turns[0][0].pk)
        qview3, _ = self._query_view(turns[3][0].pk)
        self.assertTrue(qview0.turn_collapsed)
        self.assertFalse(qview3.turn_collapsed)

    def test_active_turn_never_collapses(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        turns = self._turns(user, 3)
        # A still-streaming turn (ACTIVE query, no finished response).
        query = self._query(turns[-1][2], status=QueryStatus.ACTIVE)
        self._feed_query(query)
        resp = self._resp(query, status=ResponseStatus.ACTIVE, total=0)
        streaming = self._msg(role=MessageRole.ASSISTANT, response=resp)
        self._feed_message(streaming)
        # push it out of the tail with two more finished turns.
        extra = self._turns(streaming, 2)
        self.assertFalse(self._assistant_view(streaming.pk).turn_collapsed)
        qview, _ = self._query_view(query.pk)
        self.assertFalse(qview.turn_collapsed)
        # Finished tail turns behave normally.
        self.assertFalse(self._assistant_view(extra[-1][2].pk).turn_collapsed)

    def test_response_completion_triggers_recollapse(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        query = self._query(user, status=QueryStatus.ACTIVE)
        self._feed_query(query)
        resp = self._resp(query, status=ResponseStatus.ACTIVE, total=0)
        assistant = self._msg(role=MessageRole.ASSISTANT, response=resp)
        self._feed_message(assistant)
        # Two more turns push it out of the tail, but it is still live.
        t1 = self._turn(assistant)
        t2 = self._turn(t1[2])
        self.assertFalse(self._assistant_view(assistant.pk).turn_collapsed)
        # Completing the query + response re-runs grouping → now collapses.
        query.status = QueryStatus.SUCCESS
        query.save()
        resp.status = ResponseStatus.SUCCESS
        resp.total_time = 9.0
        resp.save()
        self.messages._on_response_updated(resp.pk, "update", {})
        self.assertTrue(self._assistant_view(assistant.pk).turn_collapsed)

    def test_block_toggle_expands_and_collapses(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        turns = self._turns(user, 3)
        first = turns[0][2]
        self.assertTrue(self._assistant_view(first.pk).turn_collapsed)
        # (show) → whole block visible, first turn offers (hide).
        self.messages.toggle_block(first.pk)
        for _, _, assistant in turns:
            self.assertFalse(self._assistant_view(assistant.pk).turn_collapsed)
        head = self._assistant_view(turns[0][2].pk)
        self.assertEqual(head.hidden_count, 0)
        self.assertTrue(head.block_pinned)
        # New turns must not clear the pin.
        self._turn(turns[-1][2])
        self.assertFalse(self._assistant_view(first.pk).turn_collapsed)
        # (hide) → back to auto-collapse.
        self.messages.toggle_block(first.pk)
        self.assertTrue(self._assistant_view(first.pk).turn_collapsed)
        self.assertFalse(self._assistant_view(first.pk).block_pinned)

    def test_second_user_message_starts_new_block(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        turns = self._turns(user, 3)
        user2 = self._msg(role=MessageRole.USER)
        self._feed_message(user2)
        _, _, assistant = self._turn(user2)
        view = self._assistant_view(assistant.pk)
        self.assertFalse(view.turn_collapsed)
        self.assertEqual(view.hidden_count, 0)
        # First block keeps its own tail + summary line.
        self.assertTrue(self._assistant_view(turns[0][2].pk).turn_collapsed)
        tail_head = self._assistant_view(turns[1][2].pk)
        self.assertFalse(tail_head.turn_collapsed)
        self.assertEqual(tail_head.hidden_count, 1)

    def test_streaming_response_row_appears_then_embeds(self):
        from ui.main.chat.messages.message import MessageView
        from ui.main.chat.messages.response import ResponseView

        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        query = self._query(user, status=QueryStatus.ACTIVE)
        self._feed_query(query)
        resp = self._resp(query, status=ResponseStatus.ACTIVE, total=0)
        # Live event inserts the streaming response right after its query,
        # auto-expanded so the tokens are visible while generating.
        self.messages._on_response_created(resp.pk, "create", {})
        items = list(self.messages.message_list)
        ridx = next(i for i, x in enumerate(items)
                    if isinstance(x, Response) and x.pk == resp.pk)
        qidx = next(i for i, x in enumerate(items)
                    if isinstance(x, Query) and x.pk == query.pk)
        self.assertEqual(ridx, qidx + 1)
        wrapper = self._wrapper(resp.pk, Response)
        self.assertIsNotNone(wrapper)
        self.assertIsInstance(wrapper.view, ResponseView)
        self.assertTrue(wrapper.view.is_open)
        self.assertEqual(wrapper.role, "response")
        # Duplicate creates are ignored.
        before = len(self.messages.message_list)
        self.messages._on_response_created(resp.pk, "create", {})
        self.assertEqual(len(self.messages.message_list), before)
        # The finished assistant message embeds the response → row removed.
        assistant = self._msg(role=MessageRole.ASSISTANT, response=resp)
        self._feed_message(assistant)
        self.assertFalse(any(
            isinstance(x, Response) and x.pk == resp.pk
            for x in self.messages.message_list
        ))
        self.assertIsNotNone(self._assistant_view(assistant.pk))

    def test_embedded_responses_never_duplicate_on_sync(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        query = self._query(user)
        self._feed_query(query)
        resp = self._resp(query)
        assistant = self._msg(role=MessageRole.ASSISTANT, response=resp)
        self._feed_message(assistant)
        self.messages._sync_standalone_responses()
        self.assertFalse(any(
            isinstance(x, Response) for x in self.messages.message_list
        ))

    def test_orphan_terminal_response_stays_visible(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        query = self._query(user)
        self._feed_query(query)
        resp = self._resp(query, status=ResponseStatus.FAILURE)
        # No assistant message references it → sync + terminal update keep it.
        self.messages._sync_standalone_responses()
        self.assertTrue(any(
            isinstance(x, Response) and x.pk == resp.pk
            for x in self.messages.message_list
        ))
        self.messages._on_response_updated(resp.pk, "update", {})
        self.assertTrue(any(
            isinstance(x, Response) and x.pk == resp.pk
            for x in self.messages.message_list
        ))

    def test_info_message_does_not_break_grouping(self):
        user = self._msg(role=MessageRole.USER)
        self._feed_message(user)
        _, _, assistant = self._turn(user)
        info = self._msg(role=MessageRole.INFO)
        self._feed_message(info)
        self.assertFalse(self._assistant_view(assistant.pk).turn_collapsed)

    # ── templates ──
    def test_hidden_line_templates_render(self):
        env = jinja2.Environment(autoescape=False)
        env.parse(AssistantMessageView.TEMPLATE_STR)
        env.parse(QueryView.TEMPLATE_STR)

        def make_view(cls, subject, **attrs):
            view = object.__new__(cls)
            view._subject_ref = subject
            view.__dict__.update(attrs)
            return view

        subj = SimpleNamespace(
            pk=1,
            session_version=SimpleNamespace(agent=SimpleNamespace(name="AgentOne")),
            response=SimpleNamespace(pk=9, status="SUCCESS", total_time=12.3,
                                     reasoning=""),
            parts=SimpleNamespace(filter=lambda **k: []),
        )
        # First visible turn with hidden predecessors: one summary line,
        # no per-turn delimiter, body still rendered (row hidden via CSS).
        head = make_view(
            AssistantMessageView, subj,
            is_reasoning_open=False, response_view=None,
            turn_collapsed=False, hidden_count=23, block_pinned=False,
            tool_list=SimpleNamespace(render=lambda: "<!--tools-->"),
        )
        out = env.from_string(AssistantMessageView.TEMPLATE_STR).render(pyview=head)
        self.assertIn("23 assistant messages hidden (show)", out)
        self.assertNotIn("turn-bar", out)
        self.assertIn("message_body_1", out)

        # Pinned-expanded block offers (hide), plain turns render nothing extra.
        pinned = make_view(
            AssistantMessageView, subj,
            is_reasoning_open=False, response_view=None,
            turn_collapsed=False, hidden_count=0, block_pinned=True,
            tool_list=SimpleNamespace(render=lambda: ""),
        )
        out = env.from_string(AssistantMessageView.TEMPLATE_STR).render(pyview=pinned)
        self.assertIn("(hide)", out)

        plain = make_view(
            AssistantMessageView, subj,
            is_reasoning_open=False, response_view=None,
            turn_collapsed=False, hidden_count=0, block_pinned=False,
            tool_list=SimpleNamespace(render=lambda: ""),
        )
        out = env.from_string(AssistantMessageView.TEMPLATE_STR).render(pyview=plain)
        self.assertNotIn("hidden-turns-bar", out)
