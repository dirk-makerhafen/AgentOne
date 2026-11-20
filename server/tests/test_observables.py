"""Write-side observables: explicit keys, the ORM mixin, and Redis fan-out.

The contract these tests pin down:

* every publishable key is produced by :mod:`runtime.observable_keys`, never
  derived generically from the model at publish time;
* a filter transition publishes **both** the old and the new value;
* an ORM write defers the fan-out to ``transaction.on_commit``;
* a tab only receives events for keys it registered.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from django.apps import apps

from runtime.observable_keys import _BUILDERS, observable_keys
from server.models import observables
from server.models.enums.message_enums import MessageRole
from server.models.workitems.enums import WorkItemStatus
from server.tests.dc_test_helpers import (
    create_agent,
    create_session,
)


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch.object(observables, "get_redis", return_value=redis):
        yield redis


def _server_models():
    return [
        model
        for model in apps.get_models()
        if model._meta.app_label == "server"
        and not model._meta.abstract
        and not model._meta.proxy
        and not model._meta.auto_created
    ]


def _no_htmx_metacharacters(key: str) -> bool:
    return not any(char in key for char in "[] ,\n\t")


# ---------------------------------------------------------------------------
# key builders
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_row_and_session_keys_are_explicit():
    agent, version = create_agent("keys-agent")
    session, sv = create_session(agent, version)
    from server.models.message import Message

    message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    keys = observable_keys(message)

    assert keys[0] == "Message"  # bare model key for unwatched all-row lists
    assert f"Message:{message.pk}" in keys
    assert f"Message.session:{session.pk}" in keys
    assert f"Message.session_version:{sv.pk}" in keys
    assert len(keys) == len(set(keys))


@pytest.mark.django_db
def test_root_session_publishes_root_and_project_variants():
    from server.models.project import Project

    agent, version = create_agent("root-agent")
    project = Project.objects.create(name="root-project")
    session, _sv = create_session(agent, version)
    session.parent_project = project
    session.save()

    keys = observable_keys(session)
    assert "SessionModel" in keys
    assert f"SessionModel:{session.pk}" in keys
    assert "SessionModel.root@is_archived:false" in keys
    assert f"SessionModel.root@project:{project.pk}@is_archived:false" in keys
    assert "SessionModel@is_active:true" in keys


@pytest.mark.django_db
def test_child_session_never_publishes_root():
    agent, version = create_agent("child-agent")
    parent, _pv = create_session(agent, version)
    from server.models.sessions.session import SessionModel

    child = SessionModel.objects.create(
        name="child",
        parent_session=parent,
        latest_session_version=parent.latest_session_version,
    )
    keys = observable_keys(child)
    assert f"SessionModel.parent_session:{parent.pk}@is_archived:false" in keys
    assert not any(key.startswith("SessionModel.root") for key in keys)


@pytest.mark.django_db
def test_archive_transition_publishes_both_values():
    agent, version = create_agent("archive-agent")
    session, _sv = create_session(agent, version)
    assert "SessionModel.root@is_archived:false" in observable_keys(session)

    session.is_archived = True
    keys = observable_keys(session, {"is_archived": False, "is_active": True})
    assert "SessionModel.root@is_archived:true" in keys
    assert "SessionModel.root@is_archived:false" in keys


@pytest.mark.django_db
def test_work_item_project_transition_publishes_terminal_filter():
    from server.models.project import Project
    from server.models.workitems.work_item import WorkItem

    project = Project.objects.create(name="work-project")
    item = WorkItem.objects.create(title="live", project=project)
    keys = observable_keys(item)

    assert "WorkItem" in keys
    assert f"WorkItem:{item.pk}" in keys
    assert f"WorkItem.project:{project.pk}" in keys
    assert f"WorkItem.project:{project.pk}@terminal:false" in keys

    item.status = WorkItemStatus.DONE
    keys = observable_keys(item, {"status": WorkItemStatus.IN_PROGRESS})
    assert f"WorkItem.project:{project.pk}@terminal:true" in keys
    assert f"WorkItem.project:{project.pk}@terminal:false" in keys


@pytest.mark.django_db
def test_cron_parenting_drops_the_root_key():
    from server.models.cron import Cronjob
    from server.models.project import Project

    cron = Cronjob.objects.create(name="root-cron", schedule="* * * * *")
    assert "Cronjob" in observable_keys(cron)
    assert "Cronjob.root@is_archived:false" in observable_keys(cron)

    project = Project.objects.create(name="cron-project")
    cron.parent_project = project
    cron.save()
    keys = observable_keys(cron)
    assert "Cronjob.root@is_archived:false" not in keys
    assert f"Cronjob.parent_project:{project.pk}@is_archived:false" in keys


@pytest.mark.django_db
def test_every_key_is_safe_inside_an_htmx_trigger():
    from server.models.sessions.session import SessionModel
    from server.models.workitems.work_item import WorkItem

    agent, version = create_agent("grammar-agent")
    parent, _pv = create_session(agent, version)
    child = SessionModel.objects.create(
        name="child", parent_session=parent, latest_session_version=parent.latest_session_version
    )
    item = WorkItem.objects.create(title="grammar")

    for instance in (parent, child, item):
        for key in observable_keys(instance):
            assert _no_htmx_metacharacters(key), key


def test_every_model_with_a_read_api_has_an_explicit_builder():
    # Explicit API models (must have key builders)
    api_models = {
        "SessionModel",
        "Message",
        "Query",
        "Response",
        "AgentTaskCall",
        "AgentModel",
        "AgentVersionModel",
        "SkillModel",
        "SkillModelVersion",
        "Cronjob",
        "DataCollection",
        "CollectionItem",
        "WorkItem",
        "Project",
        "WorkspaceModel",
        "ApiProvider",
        "AiModel",
        "TerminalSession",
    }
    missing = sorted(name for name in api_models if name not in _BUILDERS)
    assert missing == []


def test_registry_covers_every_server_model():
    # Row-only models
    row_only = {
        "AdhocToolVersion",
        "AgentTaskRun",
        "ApiKey",
        "DebugLogEntry",
        "GenericContent",
        "MessagePart",
        "QueryMessage",
        "QueryMessagePart",
        "QueryTemplateVersion",
        "ScriptsGeneration",
        "SessionAdhocTool",
        "SessionQueryTemplate",
        "SessionVersionModel",
        "SettingsModel",
        "System",
        "TaskDefinition",
        "TaskDefinitionVersion",
        "TaskInstance",
    }
    api_models = {
        "SessionModel",
        "Message",
        "Query",
        "Response",
        "AgentTaskCall",
        "AgentModel",
        "AgentVersionModel",
        "SkillModel",
        "SkillModelVersion",
        "Cronjob",
        "DataCollection",
        "CollectionItem",
        "WorkItem",
        "Project",
        "WorkspaceModel",
        "ApiProvider",
        "AiModel",
        "TerminalSession",
    }
    known = set(_BUILDERS) | api_models | row_only
    missing = sorted(
        model.__name__ for model in _server_models() if model.__name__ not in known
    )
    # GenericContent / ScriptsGeneration are row-only fallbacks.
    assert missing in ([], ["GenericContent", "ScriptsGeneration"])


# ---------------------------------------------------------------------------
# Redis client registry
# ---------------------------------------------------------------------------

def test_register_client_replaces_the_watch_set(fake_redis):
    observables.register_client("client-aaaa", ["A:1", "B:2"])
    assert observables.watch_keys("client-aaaa") == ["A:1", "B:2"]
    assert fake_redis.smembers("agentone:sse:keys:A:1") == {"client-aaaa"}

    observables.register_client("client-aaaa", ["B:2", "C:3"])
    assert observables.watch_keys("client-aaaa") == ["B:2", "C:3"]
    assert fake_redis.smembers("agentone:sse:keys:A:1") == set()
    assert fake_redis.smembers("agentone:sse:keys:C:3") == {"client-aaaa"}


def test_register_client_deduplicates_and_rejects_oversized_keys(fake_redis):
    stored = observables.register_client(
        "client-bbbb", ["A:1", "A:1", "", "x" * 201]
    )
    assert stored == ["A:1"]


def test_watch_ttl_and_heartbeat(fake_redis):
    observables.register_client("client-cccc", ["A:1"])
    assert 0 < fake_redis.ttl("agentone:sse:watch:client-cccc") <= observables.WATCH_TTL

    fake_redis.expire("agentone:sse:watch:client-cccc", 1)
    observables.touch_client("client-cccc")
    assert fake_redis.ttl("agentone:sse:watch:client-cccc") > 1


def test_reset_client_clears_the_reverse_index(fake_redis):
    observables.register_client("client-dddd", ["A:1", "B:2"])
    observables.reset_client("client-dddd")
    assert observables.watch_keys("client-dddd") == []
    assert fake_redis.smembers("agentone:sse:keys:A:1") == set()


def test_reset_client_keeps_a_live_reconnects_registration(fake_redis):
    """Cleanup must not unsubscribe a replacement stream that already owns the key set."""
    observables.register_client("client-reconnect", ["A:1"])
    pubsub = fake_redis.pubsub()
    pubsub.subscribe("agentone:sse:client-reconnect")
    pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)

    observables.reset_client("client-reconnect")
    assert observables.watch_keys("client-reconnect") == ["A:1"]

    pubsub.unsubscribe("agentone:sse:client-reconnect")
    observables.reset_client("client-reconnect")
    assert observables.watch_keys("client-reconnect") == []
    assert fake_redis.smembers("agentone:sse:keys:A:1") == set()


def test_mark_seen_returns_true_only_on_reconnect(fake_redis):
    assert observables.mark_seen("client-eeee") is False
    assert observables.mark_seen("client-eeee") is True


# ---------------------------------------------------------------------------
# fan-out
# ---------------------------------------------------------------------------

def test_fan_out_only_reaches_watching_clients(fake_redis):
    observables.register_client("client-one", ["Message.session:1"])
    observables.register_client("client-two", ["Message.session:2"])

    one = fake_redis.pubsub()
    two = fake_redis.pubsub()
    one.subscribe("agentone:sse:client-one")
    two.subscribe("agentone:sse:client-two")
    one.get_message(timeout=0.1)
    two.get_message(timeout=0.1)

    observables._fan_out(
        ["Message.session:1"],
        {"model": "Message", "pk": 5, "action": "create", "data": None},
    )

    first = one.get_message(ignore_subscribe_messages=True, timeout=0.5)
    second = two.get_message(ignore_subscribe_messages=True, timeout=0.5)
    assert first is not None
    assert second is None

    payload = json.loads(first["data"])
    assert payload["key"] == "Message.session:1"
    assert payload["model"] == "Message"
    assert payload["pk"] == 5
    assert payload["action"] == "create"


def test_fan_out_prunes_dead_clients(fake_redis):
    observables.register_client("client-dead", ["A:1"])
    fake_redis.delete("agentone:sse:watch:client-dead")

    observables._fan_out(["A:1"], {"model": "A", "pk": 1, "action": "update", "data": None})

    assert fake_redis.smembers("agentone:sse:keys:A:1") == set()


def test_publish_is_deferred_until_commit():
    instance = MagicMock()
    instance.pk = 1

    with patch.object(observables.transaction, "on_commit") as on_commit:
        observables.publish_model_event(["Message:1"], instance, "update")

    on_commit.assert_called_once()
    callback = on_commit.call_args.args[0]

    with patch.object(observables, "_fan_out") as fan_out:
        callback()
    fan_out.assert_called_once()
    keys, envelope = fan_out.call_args.args
    assert keys == ["Message:1"]
    assert envelope["pk"] == 1


def test_publish_without_keys_is_a_noop():
    instance = MagicMock()
    instance.pk = 1
    with patch.object(observables, "_fan_out") as fan_out:
        observables.publish_model_event([], instance, "update")
    fan_out.assert_not_called()


# ---------------------------------------------------------------------------
# ObservableMixin
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_save_publishes_create_then_update(monkeypatch):
    from server.models.project import Project

    calls = []
    monkeypatch.setattr(
        Project, "notify_observers", lambda self, action="update", previous=None: calls.append(
            (action, previous)
        )
    )
    project = Project.objects.create(name="mixin-project")
    assert calls[0][0] == "create"

    project.name = "renamed"
    project.save()
    action, _previous = calls[-1]
    assert action == "update"


@pytest.mark.django_db
def test_save_can_skip_publishing(monkeypatch):
    from server.models.project import Project

    calls = []
    monkeypatch.setattr(
        Project, "notify_observers", lambda self, action="update", previous=None: calls.append(action)
    )
    Project(name="quiet-project").save(publish=False)
    assert calls == []


@pytest.mark.django_db
def test_delete_publishes_with_the_original_pk(monkeypatch):
    from server.models.project import Project

    project = Project.objects.create(name="delete-project")
    published = []

    def fake_notify(self, action="update", previous=None):
        published.append((action, self.pk))

    monkeypatch.setattr(Project, "notify_observers", fake_notify)
    pk = project.pk
    project.delete()
    assert published == [("delete", pk)]
    assert project.pk is None


@pytest.mark.django_db
def test_atomic_update_publishes_the_previous_value(monkeypatch):
    from server.models.sessions.session import SessionModel

    agent, version = create_agent("atomic-agent")
    session, _sv = create_session(agent, version)

    published = []
    monkeypatch.setattr(
        SessionModel,
        "notify_observers",
        lambda self, action="update", previous=None: published.append((action, previous)),
    )

    session.atomic_update("update", is_archived=True)
    action, previous = published[-1]
    assert action == "update"
    assert previous["is_archived"] is False


@pytest.mark.django_db
def test_atomic_update_by_pk_reads_previous_values(monkeypatch):
    from server.models.sessions.session import SessionModel

    agent, version = create_agent("atomic-pk-agent")
    session, _sv = create_session(agent, version)

    captured = {}

    def fake_publish(cls, pk, action="update", data=None, previous=None):
        captured.update(pk=pk, action=action, previous=previous)

    monkeypatch.setattr(SessionModel, "publish_by_pk", classmethod(fake_publish))
    SessionModel.atomic_update_by_pk(session.pk, is_archived=True)

    assert captured["pk"] == session.pk
    assert captured["previous"]["is_archived"] is False


@pytest.mark.django_db
def test_publish_by_pk_rebuilds_keys_from_the_row(monkeypatch):
    from server.models.message import Message

    agent, version = create_agent("publish-pk-agent")
    session, sv = create_session(agent, version)
    message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )

    published = {}

    def fake_notify(self, action="update", previous=None):
        published["keys"] = observable_keys(self)
        published["action"] = action
        published["pk"] = self.pk

    monkeypatch.setattr(Message, "notify_observers", fake_notify)
    Message.publish_by_pk(message.pk, "update")

    assert published["pk"] == message.pk
    assert f"Message.session:{session.pk}" in published["keys"]
    assert "Message" in published["keys"]


@pytest.mark.django_db
def test_publish_by_pk_for_a_missing_row_is_a_noop(monkeypatch):
    from server.models.message import Message

    published = []
    monkeypatch.setattr(
        Message, "notify_observers", lambda self, action="update", previous=None: published.append(action)
    )
    Message.publish_by_pk(999_999)
    assert published == []


@pytest.mark.django_db
def test_task_call_keys_are_published_by_the_fsm_helpers(monkeypatch):
    from runtime.tasks import call_fsm
    from runtime.tasks import run_fsm
    from runtime.workitems import workitem_fsm
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.workitems.work_item import WorkItem

    paths = (
        (AgentTaskCall, call_fsm._publish_call_event),
        (AgentTaskRun, run_fsm._publish_run_event),
        (WorkItem, workitem_fsm._publish_item_event),
    )
    for model, helper in paths:
        captured = {}
        monkeypatch.setattr(
            model,
            "publish_by_pk",
            classmethod(
                lambda cls, pk, action="update", data=None, previous=None, _c=captured: _c.update(
                    pk=pk, action=action, data=data
                )
            ),
        )
        helper(42, "update", data={"status": "x"})
        assert captured == {"pk": 42, "action": "update", "data": {"status": "x"}}


def _task_call(session, sv, **overrides):
    from server.models.tasks.agent_task_call import AgentTaskCall

    fields = {
        "session": session,
        "session_version": sv,
        "requires_approval": False,
        "max_subtask_errors": 0,
        "max_subtask_error_rate": 0,
        "limit_subtask_parallel_runs": 0,
        "limit_per_instance_parallel_runs": 1,
        "max_retries": 0,
        "retry_delay": 10,
        "retry_requires_approval": True,
    }
    fields.update(overrides)
    return AgentTaskCall.objects.create(**fields)


@pytest.mark.django_db
def test_subcall_publishes_every_ancestor_call_key():
    """A descendant update must invalidate the parent's rendered sub-call tree.

    Delegated sub-calls can live in another session, so the descendant's
    ``AgentTaskCall.session`` key never reaches the parent chat.  Every
    ancestor call key is published instead, which is what the expanded tool
    card subscribes to.
    """
    from server.models.tasks.agent_task_run import AgentTaskRun

    agent, version = create_agent("ancestor-agent")
    session, sv = create_session(agent, version)

    parent = _task_call(session, sv)
    parent_run = AgentTaskRun.objects.create(
        agent_task_call=parent,
        session=session,
        session_version=sv,
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1,
    )
    child = _task_call(session, sv, parent_taskrun=parent_run)
    grandchild = _task_call(session, sv, parent_taskrun=AgentTaskRun.objects.create(
        agent_task_call=child,
        session=session,
        session_version=sv,
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1,
    ))

    child_keys = observable_keys(child)
    assert f"AgentTaskCall:{child.pk}" in child_keys
    assert f"AgentTaskCall:{parent.pk}" in child_keys
    assert f"AgentTaskCall.parent_taskrun:{parent_run.pk}" in child_keys

    grandchild_keys = observable_keys(grandchild)
    assert f"AgentTaskCall:{grandchild.pk}" in grandchild_keys
    assert f"AgentTaskCall:{child.pk}" in grandchild_keys
    assert f"AgentTaskCall:{parent.pk}" in grandchild_keys


@pytest.mark.django_db
def test_root_call_does_not_publish_ancestor_keys():
    agent, version = create_agent("root-call-agent")
    session, sv = create_session(agent, version)
    call = _task_call(session, sv)

    keys = observable_keys(call)
    assert f"AgentTaskCall:{call.pk}" in keys
    assert not any(
        key.startswith("AgentTaskCall:") and key != f"AgentTaskCall:{call.pk}"
        for key in keys
    )


@pytest.mark.django_db
def test_atomic_update_on_subcall_publishes_the_parent_call_key(monkeypatch):
    """The write path (not just the key builder) must reach ancestor cards."""
    from server.models.tasks.agent_task_run import AgentTaskRun

    agent, version = create_agent("ancestor-write-agent")
    session, sv = create_session(agent, version)
    parent = _task_call(session, sv)
    run = AgentTaskRun.objects.create(
        agent_task_call=parent,
        session=session,
        session_version=sv,
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1,
    )
    child = _task_call(session, sv, parent_taskrun=run)

    published = {}
    monkeypatch.setattr(
        observables,
        "publish_model_event",
        lambda keys, instance, action="update", data=None: published.update(keys=list(keys)),
    )
    child.atomic_update(status="ACTIVE")
    assert f"AgentTaskCall:{child.pk}" in published["keys"]
    assert f"AgentTaskCall:{parent.pk}" in published["keys"]
