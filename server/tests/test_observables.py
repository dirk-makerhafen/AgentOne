"""Tests for the Redis-backed observable registry (new ORM→UI reactive layer).

Covers ``runtime/observables.py`` (subscribe/notify/unsubscribe against
fakeredis), ``Observables`` key helpers + ``observable_keys()`` /
``notify_observers()`` (now on ``ObservableMixin`` so every ORM model is
covered), the dual-publish in ``publish_model_event``, the
``orm_subscribe`` view helper, and ``consumer.process_queue_messages``.
"""
from __future__ import annotations

import inspect
import json
from unittest.mock import MagicMock, patch

import fakeredis
from django.apps import apps
from django.test import SimpleTestCase, TestCase

from runtime import observables
from server.models.enums.message_enums import MessageRole
from server.tests.dc_test_helpers import (
    create_agent,
    create_completed_call,
    create_session,
    create_task,
)


def make_fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


class FakeInstance:
    """Minimal stand-in for PyHtmlGuiInstance (queue dispatch side)."""

    def __init__(self, instance_key="test-instance"):
        from ui.lib.pyHtmlGui.pyhtmlgui.lib.weakFunctionReferences import (
            WeakFunctionReferences,
        )

        self.instance_key = instance_key
        self._function_references = WeakFunctionReferences()
        self.observed_views = {}


class RegistryTest(SimpleTestCase):
    """subscribe/notify/unsubscribe/unsubscribe_all against fakeredis."""

    def setUp(self):
        self.redis = make_fake_redis()
        self.patch = patch.object(observables, "get_redis", return_value=self.redis)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_subscribe_registers_function_id(self):
        observables.subscribe("inst-1", "Message.session:5", 42)
        self.assertEqual(
            json.loads(self.redis.hget("agentone:obs:Message.session:5", "inst-1")),
            [42],
        )
        self.assertEqual(
            self.redis.smembers("agentone:uikeys:inst-1"), {"Message.session:5"}
        )

    def test_subscribe_is_idempotent(self):
        observables.subscribe("inst-1", "Message.session:5", 42)
        observables.subscribe("inst-1", "Message.session:5", 42)
        self.assertEqual(
            json.loads(self.redis.hget("agentone:obs:Message.session:5", "inst-1")),
            [42],
        )

    def test_notify_queues_only_for_subscribers(self):
        observables.subscribe("inst-1", "Message.session:5", 42)
        observables.notify(["Message.session:5", "Message.session:6"], "Message", 9, "create")
        queued = self.redis.lrange("agentone:uiq:inst-1", 0, -1)
        self.assertEqual(len(queued), 1)
        msg = json.loads(queued[0])
        self.assertEqual(msg["key"], "Message.session:5")
        self.assertEqual(msg["keys"], ["Message.session:5"])
        self.assertEqual(msg["model"], "Message")
        self.assertEqual(msg["pk"], 9)
        self.assertEqual(msg["action"], "create")
        self.assertEqual(msg["function_ids"], [42])
        # No subscriber for session 6 → no second queue, no queue at all.
        self.assertEqual(self.redis.llen("agentone:uiq:nobody"), 0)

    def test_notify_merges_keys_but_keeps_all(self):
        observables.subscribe("inst-1", "Message", 7)
        observables.subscribe("inst-1", "Message.session:5", 8)
        observables.notify(["Message", "Message.session:5"], "Message", 9, "update")
        msg = json.loads(self.redis.lrange("agentone:uiq:inst-1", 0, -1)[0])
        self.assertEqual(sorted(msg["function_ids"]), [7, 8])
        self.assertEqual(sorted(msg["keys"]), ["Message", "Message.session:5"])

    def test_notify_empty_keys_is_noop(self):
        observables.notify([], "Message", 9, "create")
        self.assertEqual(self.redis.keys("agentone:uiq:*"), [])

    def test_unsubscribe_removes_function_id(self):
        observables.subscribe("inst-1", "Message.session:5", 42)
        observables.subscribe("inst-1", "Message.session:5", 43)
        observables.unsubscribe("inst-1", "Message.session:5", 42)
        self.assertEqual(
            json.loads(self.redis.hget("agentone:obs:Message.session:5", "inst-1")),
            [43],
        )
        observables.unsubscribe("inst-1", "Message.session:5", 43)
        self.assertIsNone(self.redis.hget("agentone:obs:Message.session:5", "inst-1"))
        self.assertEqual(self.redis.smembers("agentone:uikeys:inst-1"), set())

    def test_unsubscribe_all_cleans_everything(self):
        observables.subscribe("inst-1", "Message.session:5", 42)
        observables.subscribe("inst-1", "Query.session:5", 43)
        observables.notify(["Message.session:5"], "Message", 1, "create")
        observables.unsubscribe_all("inst-1")
        self.assertEqual(self.redis.keys("agentone:obs:*"), [])
        self.assertEqual(self.redis.keys("agentone:uiq:*"), [])
        self.assertEqual(self.redis.keys("agentone:uikeys:*"), [])


class ObservablesKeysTest(TestCase):
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

        project = Project.objects.create(name="obs-proj", path="/tmp")
        self.assertEqual(
            project.observables.child_agents,
            f"AgentModel.parent_project:{project.pk}",
        )

    def test_notify_observers_end_to_end(self):
        agent, av = create_agent("obs-agent3")
        session, sv = create_session(agent, av)
        from server.models.message import Message

        msg = Message.objects.create(
            role=MessageRole.USER, session=session, session_version=sv,
        )
        with patch.object(observables, "get_redis", return_value=make_fake_redis()) as _:
            import runtime.observables as obs_module

            r = obs_module.get_redis()
            observables.subscribe("inst-9", f"Message.session:{session.pk}", 11)
            msg.notify_observers("create")
            queued = r.lrange("agentone:uiq:inst-9", 0, -1)
            self.assertEqual(len(queued), 1)
            payload = json.loads(queued[0])
            self.assertEqual(payload["model"], "Message")
            self.assertEqual(payload["pk"], msg.pk)
            self.assertEqual(payload["action"], "create")
            self.assertEqual(payload["function_ids"], [11])


class PublishDualPublishTest(TestCase):
    """publish_model_event feeds the redis registry (no channel layer involved)."""

    def test_dual_publish(self):
        from runtime.events import publish_model_event

        agent, av = create_agent("obs-agent4")
        session, sv = create_session(agent, av)
        from server.models.message import Message

        msg = Message.objects.create(
            role=MessageRole.USER, session=session, session_version=sv,
        )
        fake = make_fake_redis()
        with patch.object(observables, "get_redis", return_value=fake):
            observables.subscribe("inst-7", f"Message.session:{session.pk}", 21)
            publish_model_event(msg, "create")
            queued = fake.lrange("agentone:uiq:inst-7", 0, -1)
            self.assertEqual(len(queued), 1)
            self.assertEqual(json.loads(queued[0])["action"], "create")

    def test_non_observable_instance_still_ok(self):
        from runtime.events import publish_model_event

        instance = MagicMock()
        instance._meta.model_name = "test"
        instance._meta.app_label = "test"
        instance._meta.fields = []
        instance.pk = 1
        del instance.notify_observers  # instances without notify support
        publish_model_event(instance, "create")  # must not raise


class OrmSubscribeTest(SimpleTestCase):
    """orm_subscribe/orm_unsubscribe_view bookkeeping."""

    def setUp(self):
        self.redis = make_fake_redis()
        self.patch = patch.object(observables, "get_redis", return_value=self.redis)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def _view(self):
        view = MagicMock()
        view._instance = FakeInstance()
        view._observed_function_ids = []
        return view

    def test_subscribe_and_unsubscribe(self):
        from ui.lib.model_view import orm_subscribe, orm_unsubscribe_view

        class Cb:
            def on_event(self, **kwargs):
                pass

        view = self._view()
        fid = orm_subscribe(view, "Message.session:5", Cb().on_event)
        self.assertIsNotNone(fid)
        self.assertEqual(
            json.loads(self.redis.hget("agentone:obs:Message.session:5", "test-instance")),
            [fid],
        )
        self.assertEqual(view._instance.observed_views["Message.session:5"], [fid])
        orm_unsubscribe_view(view)
        self.assertIsNone(
            self.redis.hget("agentone:obs:Message.session:5", "test-instance")
        )
        self.assertEqual(view._observed_function_ids, [])


class ProcessQueueMessagesTest(SimpleTestCase):
    """Loop dispatch coalesces per function_id and skips dead callbacks."""

    def test_coalesce_and_dispatch(self):
        from ui.consumer import process_queue_messages

        instance = FakeInstance()
        calls = []

        class View:
            def on_event(self, **kwargs):
                calls.append(kwargs)

        view = View()
        fid = instance._function_references.add(view.on_event)
        process_queue_messages(instance, [
            {"key": "K1", "model": "M", "pk": 1, "action": "create",
             "data": {}, "function_ids": [fid, 999999]},
            {"key": "K2", "model": "M", "pk": 2, "action": "update",
             "data": {"x": 1}, "function_ids": [fid]},
        ])
        # One call (latest message wins), unknown fid skipped.
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["pk"], 2)
        self.assertEqual(calls[0]["data"], {"x": 1})

    def test_dead_weakref_skipped(self):
        from ui.consumer import process_queue_messages

        instance = FakeInstance()

        class View:
            def on_event(self, **kwargs):
                raise AssertionError("must not be called")

        fid = instance._function_references.add(View().on_event)
        import gc

        gc.collect()
        # No exception, no call.
        process_queue_messages(instance, [
            {"key": "K", "model": "M", "pk": 1, "action": "create",
             "data": {}, "function_ids": [fid]},
        ])


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
        from server.models.base_model import ObservableMixin

        missing = []
        for m in self._server_models():
            prop = inspect.getattr_static(m, "observables", None)
            if not isinstance(prop, property) or not issubclass(m, ObservableMixin):
                missing.append(m.__name__)
        self.assertEqual(missing, [])


class PlainModelsObservableTest(TestCase):
    """Instance-level checks for the non-BaseModel mixins."""

    def test_workspace_notify_end_to_end(self):
        from server.models.workspace import WorkspaceModel

        ws = WorkspaceModel.objects.create(name="obs-ws", path="/tmp")
        self.assertEqual(ws.observables.any, "WorkspaceModel")
        self.assertIn("WorkspaceModel", ws.observable_keys())
        self.assertIn(f"WorkspaceModel.pk:{ws.pk}", ws.observable_keys())
        fake = make_fake_redis()
        with patch.object(observables, "get_redis", return_value=fake):
            observables.subscribe("inst-ws", "WorkspaceModel", 31)
            ws.notify_observers("create")
            queued = fake.lrange("agentone:uiq:inst-ws", 0, -1)
            self.assertEqual(len(queued), 1)
            self.assertEqual(json.loads(queued[0])["model"], "WorkspaceModel")

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

        project = Project.objects.create(name="obs-proj2", path="/tmp")
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
