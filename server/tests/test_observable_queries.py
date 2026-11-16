"""Tests for the read-side observable API.

The important invariant is cross-side: every key a list subscribes to must be
a key the write side actually publishes for a row in that state.  A list that
filters on something the publisher never emits would silently go stale.
"""
from __future__ import annotations

import pytest
from django.apps import apps

from runtime.observable_keys import observable_keys
from runtime.observable_queries import (
    ObservableList,
    ObservableValue,
    RowObservables,
    api_for,
    pk_key,
    relation_key,
    root_key,
)
from runtime.observable_queries.agents import AgentObservables, SkillObservables
from runtime.observable_queries.conversation import (
    MessageObservables,
    QueryObservables,
    ResponseObservables,
    TaskCallObservables,
)
from runtime.observable_queries.sessions import SessionObservables
from runtime.observable_queries.structure import (
    AiModelObservables,
    ProjectObservables,
    ProviderObservables,
    TerminalObservables,
    WorkspaceObservables,
)
from runtime.observable_queries.work import (
    CollectionObservables,
    CronjobObservables,
    WorkItemObservables,
)
from server.models.enums.message_enums import MessageRole
from server.models.workitems.enums import WorkItemStatus
from server.tests.dc_test_helpers import (
    create_agent,
    create_completed_call,
    create_data_collection,
    create_session,
    create_task,
)


def _published(instance) -> set[str]:
    return set(observable_keys(instance))


def _assert_subscribed(result, instance):
    assert isinstance(result, ObservableList)
    assert isinstance(result.rows, tuple)
    assert result.keys
    missing = set(result.keys) - _published(instance)
    assert not missing, f"{result.keys} not published by {instance!r}: {missing}"


# ---------------------------------------------------------------------------
# helpers / registry coverage
# ---------------------------------------------------------------------------

def test_key_helpers_accept_models_and_names():
    from server.models.message import Message

    assert pk_key(Message, 3) == "Message:3"
    assert pk_key("Message", 3) == "Message:3"
    assert relation_key(Message, "session", 4) == "Message.session:4"
    assert relation_key("Message", "session", 4) == "Message.session:4"
    assert root_key(Message) == "Message.root"
    assert root_key("Message") == "Message.root"


def test_every_server_model_has_a_read_api():
    missing = []
    for model in apps.get_models():
        if model._meta.app_label != "server":
            continue
        if model._meta.abstract or model._meta.proxy or model._meta.auto_created:
            continue
        try:
            api_for(model)
        except KeyError:
            missing.append(model.__name__)
    assert missing == []


def test_row_only_api_is_by_primary_key():
    api = api_for("DebugLogEntry")
    assert isinstance(api, RowObservables)
    with pytest.raises(AttributeError):
        api.root  # pylint: disable=pointless-statement


def test_observable_list_does_not_expose_a_queryset():
    assert not hasattr(ObservableList, "filter")
    assert not hasattr(ObservableValue, "filter")


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_root_sessions_subscribe_to_the_active_filter():
    agent, version = create_agent("query-root-agent")
    session, _sv = create_session(agent, version)

    result = SessionObservables().root()
    assert [row.pk for row in result.rows] == [session.pk]
    assert result.keys == ("SessionModel.root@is_archived:false",)
    _assert_subscribed(result, session)


@pytest.mark.django_db
def test_archived_sessions_are_excluded_from_the_default_root():
    from server.models.sessions.session import SessionModel

    agent, version = create_agent("query-archived-agent")
    live, _ = create_session(agent, version)
    gone, _ = create_session(agent, version)
    SessionModel.objects.filter(pk=gone.pk).update(is_archived=True)

    rows = SessionObservables().root()
    assert [row.pk for row in rows.rows] == [live.pk]
    assert "SessionModel.root@is_archived:true" not in rows.keys


@pytest.mark.django_db
def test_project_scoped_root_key_matches_the_writer():
    from server.models.project import Project
    from server.models.sessions.session import SessionModel

    agent, version = create_agent("query-project-agent")
    project = Project.objects.create(name="query-project")
    session, _sv = create_session(agent, version)
    SessionModel.objects.filter(pk=session.pk).update(parent_project=project)
    session.refresh_from_db()

    result = SessionObservables().root(project_id=project.pk)
    assert [row.pk for row in result.rows] == [session.pk]
    assert result.keys == (
        f"SessionModel.root@project:{project.pk}@is_archived:false",
    )
    _assert_subscribed(result, session)


@pytest.mark.django_db
def test_children_and_by_project_keys():
    from server.models.project import Project
    from server.models.sessions.session import SessionModel

    agent, version = create_agent("query-child-agent")
    parent, _pv = create_session(agent, version)
    project = Project.objects.create(name="query-child-project")
    child = SessionModel.objects.create(
        name="child",
        parent_session=parent,
        parent_project=project,
        latest_session_version=parent.latest_session_version,
    )

    children = SessionObservables().children(parent.pk)
    assert [row.pk for row in children.rows] == [child.pk]
    _assert_subscribed(children, child)

    by_project = SessionObservables().by_project(project.pk)
    assert {row.pk for row in by_project.rows} == {child.pk}
    _assert_subscribed(by_project, child)


@pytest.mark.django_db
def test_active_subagent_count_uses_the_active_key():
    agent, version = create_agent("query-count-agent")
    parent, _pv = create_session(agent, version)
    from server.models.sessions.session import SessionModel

    SessionModel.objects.create(
        name="sub",
        parent_session=parent,
        is_active=True,
        latest_session_version=parent.latest_session_version,
    )

    value = SessionObservables().active_subagent_count()
    assert isinstance(value, ObservableValue)
    assert value.value == 1
    assert value.keys == ("SessionModel@is_active:true",)


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_conversation_lists_subscribe_to_their_rows():
    from server.models.message import Message
    from server.models.queries.query import Query

    agent, version = create_agent("query-conv-agent")
    session, sv = create_session(agent, version)
    message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    query = Query.objects.create(
        session=session, session_version=sv, trigger_message=message
    )
    response = query.related_response.create(
        session=session, session_version=sv
    )
    task = create_task("query-conv-task", agent=agent)
    call = create_completed_call(agent, task, session, sv)

    for api, instance, pk in (
        (MessageObservables(), message, message.pk),
        (QueryObservables(), query, query.pk),
        (ResponseObservables(), response, response.pk),
        (TaskCallObservables(), call, call.pk),
    ):
        by_session = api.by_session(session.pk)
        assert pk in {row.pk for row in by_session.rows}
        assert by_session.keys == (f"{type(instance).__name__}.session:{session.pk}",)
        _assert_subscribed(by_session, instance)

        by_pk = api.by_pk(pk)
        assert by_pk.keys == (f"{type(instance).__name__}:{pk}",)
        _assert_subscribed(by_pk, instance)


@pytest.mark.django_db
def test_responses_by_query_are_subscribed():
    from server.models.queries.query import Query

    agent, version = create_agent("query-response-agent")
    session, sv = create_session(agent, version)
    query = Query.objects.create(session=session, session_version=sv)
    response = query.related_response.create(session=session, session_version=sv)

    result = ResponseObservables().by_query(query.pk)
    assert [row.pk for row in result.rows] == [response.pk]
    _assert_subscribed(result, response)


# ---------------------------------------------------------------------------
# agents / skills / structure
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_agent_and_skill_lists_use_bare_model_keys():
    agent, _version = create_agent("query-list-agent")
    assert AgentObservables().root().keys == ("AgentModel",)
    assert SkillObservables().root().keys == ("SkillModel",)


@pytest.mark.django_db
def test_agents_by_parent_project_subscribe_to_the_archive_filter():
    from server.models.agents.agent import AgentModel
    from server.models.project import Project

    project = Project.objects.create(name="query-agent-project")
    agent = AgentModel.objects.create(name="query-parent-agent", parent_project=project)

    result = AgentObservables().by_parent_project(project.pk)
    assert [row.pk for row in result.rows] == [agent.pk]
    _assert_subscribed(result, agent)


@pytest.mark.django_db
def test_projects_workspaces_and_providers():
    from server.models.project import Project
    from server.models.providers.api_provider import ApiProvider
    from server.models.workspace import WorkspaceModel

    project = Project.objects.create(name="query-project-list")
    workspace = WorkspaceModel.objects.create(name="ws", path="/tmp/ws")
    provider = ApiProvider.objects.create(name="prov")

    assert ProjectObservables().root().keys == ("Project.root",)
    assert [row.pk for row in ProjectObservables().by_pk(project.pk).rows] == [project.pk]

    root_ws = WorkspaceObservables().root()
    assert "WorkspaceModel" in root_ws.keys
    assert [row.pk for row in ProviderObservables().root().rows] == [provider.pk]


@pytest.mark.django_db
def test_workspace_by_project_key():
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel

    project = Project.objects.create(name="query-ws-project")
    workspace = WorkspaceModel.objects.create(
        name="nested-ws", path="/tmp/nested", parent_project=project
    )

    result = WorkspaceObservables().by_project(project.pk)
    assert [row.pk for row in result.rows] == [workspace.pk]
    _assert_subscribed(result, workspace)


@pytest.mark.django_db
def test_terminals_and_ai_models_subscribe_to_their_owner():
    from server.models.providers.ai_model import AiModel
    from server.models.providers.api_provider import ApiProvider
    from server.models.terminal import TerminalSession

    agent, version = create_agent("query-terminal-agent")
    session, _sv = create_session(agent, version)
    terminal = TerminalSession.objects.create(
        session=session, tmux_session_name="tmux-query-test"
    )
    provider = ApiProvider.objects.create(name="query-provider")
    model = AiModel.objects.create(name="query-model", api_provider=provider)

    terminal_list = TerminalObservables().by_session(session.pk)
    assert [row.pk for row in terminal_list.rows] == [terminal.pk]
    _assert_subscribed(terminal_list, terminal)

    model_list = AiModelObservables().by_provider(provider.pk)
    assert [row.pk for row in model_list.rows] == [model.pk]
    _assert_subscribed(model_list, model)


# ---------------------------------------------------------------------------
# cron / collections / work items
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cron_lists_and_project_filter():
    from server.models.cron import Cronjob
    from server.models.project import Project

    project = Project.objects.create(name="query-cron-project")
    cron = Cronjob.objects.create(
        name="query-cron", schedule="* * * * *", parent_project=project
    )

    assert CronjobObservables().root().keys == ("Cronjob",)
    by_project = CronjobObservables().by_project(project.pk)
    assert [row.pk for row in by_project.rows] == [cron.pk]
    _assert_subscribed(by_project, cron)


@pytest.mark.django_db
def test_collection_lists():
    from server.models.collections.collection_item import CollectionItem
    from server.models.project import Project

    project = Project.objects.create(name="query-collection-project")
    collection = create_data_collection("query-collection", parent_project=project)
    item = CollectionItem.objects.create(
        collection=collection, member="m", score=1.0, value={}
    )

    assert CollectionObservables().root().keys == ("DataCollection",)
    by_project = CollectionObservables().by_project(project.pk)
    assert [row.pk for row in by_project.rows] == [collection.pk]
    _assert_subscribed(by_project, collection)

    from runtime.observable_queries.work import CollectionItemObservables

    items = CollectionItemObservables().by_collection(collection.pk)
    assert [row.pk for row in items.rows] == [item.pk]
    _assert_subscribed(items, item)


@pytest.mark.django_db
def test_work_item_lists_expose_the_terminal_filter():
    from server.models.project import Project
    from server.models.workitems.work_item import WorkItem

    project = Project.objects.create(name="query-work-project")
    live = WorkItem.objects.create(title="live", project=project)
    done = WorkItem.objects.create(
        title="done", project=project, status=WorkItemStatus.DONE
    )

    root = WorkItemObservables().root()
    assert root.keys == ("WorkItem",)
    assert {row.pk for row in root.rows} == {live.pk}

    archived_root = WorkItemObservables().root(terminal=True)
    assert {row.pk for row in archived_root.rows} == {live.pk, done.pk}

    by_project = WorkItemObservables().by_project(project.pk)
    assert {row.pk for row in by_project.rows} == {live.pk}
    _assert_subscribed(by_project, live)

    terminal = WorkItemObservables().by_project(project.pk, terminal=True)
    assert {row.pk for row in terminal.rows} == {live.pk, done.pk}
    _assert_subscribed(terminal, done)
