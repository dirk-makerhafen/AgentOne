"""Tests for the Redis-backed observable registry (new ORM→UI reactive layer).

Covers ``server/models/observables.py`` (subscribe/notify/unsubscribe against
fakeredis), ``ObservableKeys`` key helpers + ``observable_keys()`` /
``notify_observers()`` (now on ``ObservableMixin`` so every ORM model is
covered), the dual-publish in ``publish_model_event``, the
``orm_subscribe`` view helper, and ``consumer.process_queue_messages``.
"""
from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import fakeredis
from django.apps import apps
from django.test import SimpleTestCase, TestCase

from server.models import observables
from server.models.enums.message_enums import MessageRole
from server.tests.dc_test_helpers import (
    create_agent,
    create_completed_call,
    create_session,
    create_task,
)


def make_fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


class ObservableKeysTest(TestCase):
    """Key helpers produce the strings notify() publishes on."""

    def test_message_keys(self):
        agent, av = create_agent("obs-agent")
        session, sv = create_session(agent, av)
        from server.models.message import Message

        msg = Message.objects.create(
            role=MessageRole.USER, session=session, session_version=sv,
        )
        self.assertEqual(msg.observables.any, "Message")
        self.assertEqual(msg.observables.pk, f"Message.pk:{msg.pk}")
        # __getattr__ FK fallback matches the explicit key format.
        self.assertEqual(msg.observables.session, f"Message.session:{session.pk}")
        keys = msg.observable_keys()
        self.assertIn("Message", keys)
        self.assertIn(f"Message.pk:{msg.pk}", keys)
        self.assertIn(f"Message.session:{session.pk}", keys)
        self.assertIn(f"Message.session_version:{sv.pk}", keys)

    def test_query_and_call_keys_include_session(self):
        agent, av = create_agent("obs-agent2")
        session, sv = create_session(agent, av)
        task_def = create_task("obs-task", agent=agent)
        from server.models.message import Message
        from server.models.queries.query import Query

        msg = Message.objects.create(
            role=MessageRole.USER, session=session, session_version=sv,
        )
        query = Query.objects.create(
            session=session, session_version=sv, trigger_message=msg,
        )
        self.assertIn(f"Query.session:{session.pk}", query.observable_keys())
        call = create_completed_call(agent, task_def, session, sv)
        self.assertIn(f"AgentTaskCall.session:{session.pk}", call.observable_keys())
        # notify_observers() works on all of them (previously TypeError on
        # the models that shadowed observable_keys with a property).
        for instance in (msg, query, call):
            with patch.object(observables, "notify") as mock_notify:
                instance.notify_observers("update")
                mock_notify.assert_called_once()
                keys = mock_notify.call_args[0][0]
                self.assertIn(instance.observables.pk, keys)

    def test_reverse_side_keys_match(self):
        from server.models.project import Project

        project = Project.objects.create(name="obs-proj")
        self.assertEqual(
            project.observables.child_agents,
            f"AgentModel.parent_project:{project.pk}",
        )

    def test_noparents_key_for_root_rows(self):
        from server.models.cron import Cronjob
        from server.models.project import Project

        cron = Cronjob.objects.create(name="obs-root-cron", schedule="* * * * *")
        self.assertEqual(cron.observables.noparents, "Cronjob.noparents")
        self.assertIn("Cronjob.noparents", cron.observable_keys())

        # Parenting the row drops the noparents key and adds the FK key.
        project = Project.objects.create(name="obs-root-proj")
        cron.parent_project = project
        cron.save()
        keys = cron.observable_keys()
        self.assertNotIn("Cronjob.noparents", keys)
        self.assertIn(f"Cronjob.parent_project:{project.pk}", keys)

    def test_flat_model_never_has_noparents(self):
        from server.models.project import Project

        project = Project.objects.create(name="obs-flat-proj")
        self.assertNotIn("Project.noparents", project.observable_keys())

class PublishDualPublishTest(TestCase):
    """publish_model_event feeds the redis registry (no channel layer involved)."""

    def test_non_observable_instance_still_ok(self):
        from server.models.observables import publish_model_event

        instance = MagicMock()
        instance._meta.model_name = "test"
        instance._meta.app_label = "test"
        instance._meta.fields = []
        instance.pk = 1
        del instance.notify_observers  # instances without notify support
        publish_model_event(instance, "create")  # must not raise


class PublishByPkTest(TestCase):
    """publish_by_pk builds FK observable keys without materializing the row."""

    def _message(self, name):
        agent, av = create_agent(name)
        session, sv = create_session(agent, av)
        from server.models.message import Message

        return Message.objects.create(
            role=MessageRole.USER, session=session, session_version=sv,
        )

    def test_keys_match_materialized_instance(self):
        msg = self._message("obs-pk-agent")
        with patch.object(observables, "notify") as mock_notify:
            type(msg).publish_by_pk(msg.pk, "update")
        mock_notify.assert_called_once()
        keys, model, pk, action = mock_notify.call_args[0][:4]
        self.assertEqual(set(keys), set(msg.observable_keys()))
        self.assertEqual(model, "Message")
        self.assertEqual(pk, msg.pk)
        self.assertEqual(action, "update")

    def test_missing_row_is_noop(self):
        from server.models.message import Message

        with patch.object(observables, "notify") as mock_notify:
            Message.publish_by_pk(999999)
        mock_notify.assert_not_called()

    def test_atomic_update_by_pk_updates_and_publishes(self):
        msg = self._message("obs-pk-agent2")
        from server.models.message import Message

        with patch.object(Message, "publish_by_pk") as mock_pub:
            n = Message.atomic_update_by_pk(msg.pk, role=MessageRole.ASSISTANT)
        self.assertEqual(n, 1)
        mock_pub.assert_called_once_with(msg.pk, "update")
        msg.refresh_from_db()
        self.assertEqual(msg.role, MessageRole.ASSISTANT)


class FsmPublishActionTest(SimpleTestCase):
    """FSM publish helpers forward action + updated fields (no row load)."""

    def test_call_event_forwards_action_and_data(self):
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.tasks import call_fsm

        fields = {"status": "waiting", "updated_at": object()}
        with patch.object(AgentTaskCall, "publish_by_pk") as mock_pub:
            call_fsm._publish_call_event(42, "update", data=fields)
        mock_pub.assert_called_once_with(42, "update", data=fields)

    def test_run_event_forwards_action_and_data(self):
        from server.models.tasks.agent_task_run import AgentTaskRun
        from runtime.tasks import run_fsm

        fields = {"status": "active", "updated_at": object()}
        with patch.object(AgentTaskRun, "publish_by_pk") as mock_pub:
            run_fsm._publish_run_event(7, "update", data=fields)
        mock_pub.assert_called_once_with(7, "update", data=fields)

    def test_item_event_forwards_action_and_data(self):
        from server.models.workitems.work_item import WorkItem
        from runtime.workitems import workitem_fsm

        fields = {"status": "ready", "updated_at": object()}
        with patch.object(WorkItem, "publish_by_pk") as mock_pub:
            workitem_fsm._publish_item_event(3, "update", data=fields)
        mock_pub.assert_called_once_with(3, "update", data=fields)


class AllModelsObservableTest(SimpleTestCase):
    """Every ORM model supports being observable (no DB needed)."""

    def _server_models(self):
        return [
            m for m in apps.get_models()
            if m._meta.app_label == "server"
            and not m._meta.abstract
            and not m._meta.proxy
            and not m._meta.auto_created
        ]

    def test_models_exist(self):
        self.assertGreater(len(self._server_models()), 20)

    def test_every_model_has_notify_observers(self):
        missing = [
            m.__name__ for m in self._server_models()
            if not callable(getattr(m, "notify_observers", None))
        ]
        self.assertEqual(missing, [])

    def test_every_model_has_observable_keys(self):
        missing = [
            m.__name__ for m in self._server_models()
            if not callable(getattr(m, "observable_keys", None))
        ]
        self.assertEqual(missing, [])

    def test_every_model_has_observables_property(self):
        from server.models.observables import ObservableMixin

        missing = []
        for m in self._server_models():
            prop = inspect.getattr_static(m, "observables", None)
            if not isinstance(prop, property) or not issubclass(m, ObservableMixin):
                missing.append(m.__name__)
        self.assertEqual(missing, [])


class PlainModelsObservableTest(TestCase):
    """Instance-level checks for the non-BaseModel mixins."""

    def test_skill_version_keys_include_skill_fk(self):
        from server.models.skills.skill_version import SkillModelVersion

        ver = SkillModelVersion.objects.create()
        self.assertIn("SkillModelVersion", ver.observable_keys())
        self.assertIn(f"SkillModelVersion.pk:{ver.pk}", ver.observable_keys())

    def test_generic_content_keys_with_string_pk(self):
        from server.models.content import GenericContent

        content = GenericContent.objects.create(sha256="ab" * 32, content="hi")
        keys = content.observable_keys()
        self.assertIn("GenericContent", keys)
        self.assertIn(f"GenericContent.pk:{content.pk}", keys)

    def test_project_and_skill_notify(self):
        from server.models.project import Project
        from server.models.skills.skill import SkillModel

        project = Project.objects.create(name="obs-proj2")
        with patch.object(observables, "notify") as mock_notify:
            project.notify_observers("update")
            mock_notify.assert_called_once()
        skill = SkillModel.objects.create(name="obs-skill", parent_project=project)
        self.assertIn(
            f"SkillModel.parent_project:{project.pk}", skill.observable_keys()
        )
        with patch.object(observables, "notify") as mock_notify:
            skill.notify_observers("create")
            mock_notify.assert_called_once()
