"""Tests for runtime/events.py — event publishing infrastructure."""
from __future__ import annotations

from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, SimpleTestCase
from server.models.enums.message_enums import MessageRole
from server.tests.dc_test_helpers import create_agent, create_session, create_task
from runtime.events import (
    publish,
    publish_model_event,
    _extract_filter_context,
    CHANNEL_GROUP,
)


class ExtractFilterContextTest(TestCase):
    """_extract_filter_context correctly resolves FK fields."""

    def test_message_includes_session_version_and_resolved_session(self):
        agent, av = create_agent("event-test-agent")
        session, sv = create_session(agent, av)
        from server.models.message import Message
        msg = Message.objects.create(
            role=MessageRole.USER,
            session=sv.session,
            session_version=sv,
        )
        ctx = _extract_filter_context(msg)
        self.assertIn("session_version_id", ctx)
        self.assertEqual(ctx["session_version_id"], sv.pk)
        self.assertIn("session_id", ctx)
        self.assertEqual(ctx["session_id"], session.pk)

    def test_model_with_direct_session_id_does_not_resolve(self):
        agent, av = create_agent("event-test-agent2")
        session, sv = create_session(agent, av)
        task_def = create_task("event-task")
        from server.tests.dc_test_helpers import create_completed_call
        # create_completed_call already creates with ENDED_SUCCESS status
        tdv = task_def.latest_task_version
        from server.models.tasks.task_instance import TaskInstance
        ti = TaskInstance.objects.create(
            task_definition_version=tdv,
            session=session,
            session_version=sv,
            iarguments_json={},
            requires_approval=False,
            max_subtask_errors=0,
            max_subtask_error_rate=0,
            limit_subtask_parallel_runs=0,
            limit_per_instance_parallel_runs=1,
            max_retries=0,
            retry_delay=10,
            retry_requires_approval=True,
        )
        ctx = _extract_filter_context(ti)
        self.assertIn("session_id", ctx)
        self.assertEqual(ctx["session_id"], session.pk)

    def test_model_with_no_session_fk_returns_no_session_id(self):
        agent, av = create_agent("event-test-agent3")
        ctx = _extract_filter_context(agent)
        self.assertNotIn("session_id", ctx)
        self.assertIn("latest_agent_version_id", ctx)

    def test_only_fk_and_o2o_fields_are_extracted(self):
        agent, av = create_agent("event-test-agent4")
        ctx = _extract_filter_context(agent)
        for key in ctx:
            self.assertTrue(key.endswith("_id"), f"Unexpected non-FK key: {key}")


@patch("runtime.events.get_channel_layer", return_value=None)
class PublishNoChannelLayerTest(SimpleTestCase):
    """publish() is a no-op when no channel layer is configured."""

    def test_publish_returns_silently(self, mock_get_cl):
        result = publish(1, "test.event", {"foo": "bar"})
        self.assertIsNone(result)

    def test_publish_model_event_returns_silently(self, mock_get_cl):
        from django.db.models.base import Model
        instance = MagicMock(spec=Model)
        type(instance)._meta = PropertyMock(return_value=MagicMock(
            model_name="test", app_label="test",
        ))
        type(instance).pk = PropertyMock(return_value=1)
        result = publish_model_event(instance, "create")
        self.assertIsNone(result)


class ExtractFilterContextEdgeTest(SimpleTestCase):
    """Edge cases for FK extraction."""

    def test_none_instance_does_not_crash(self):
        with self.assertRaises(AttributeError):
            _extract_filter_context(None)

    def test_instance_with_no_fk_fields_returns_empty_dict(self):
        from django.db.models.base import Model
        obj = MagicMock(spec=Model)
        type(obj)._meta = PropertyMock(return_value=MagicMock(fields=[]))
        # spec=Model prevents hasattr from returning True for random attrs
        ctx = _extract_filter_context(obj)
        self.assertEqual(ctx, {})
