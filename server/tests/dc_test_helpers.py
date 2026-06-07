"""Shared fixture helpers for data-collection tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.collections import DataCollection, CollectionItem
from server.models.enums.task_enums import TaskCallStatusDetail, TaskType
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.tasks.task_instance import TaskInstance
from server.models.tasks.agent_task_call import AgentTaskCall

TESTPROJECT = Path(__file__).parent / "testproject" / ".agentone"


def create_agent(name: str = "test-agent") -> tuple[AgentModel, AgentVersionModel]:
    agent = AgentModel.objects.create(name=name)
    av = AgentVersionModel.objects.create(agent=agent)
    AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=av)
    agent.refresh_from_db()
    return agent, av


def create_task(
    name: str,
    group: str = "",
    task_type: str = TaskType.TOOL,
    agent: AgentModel | None = None,
) -> TaskDefinition:
    td = TaskDefinition.objects.create(
        name=name, group_name=group, parent_agent=agent,
    )
    tdv = TaskDefinitionVersion.objects.create(
        task_definition=td,
        description="test",
        function_schema={"type": "object", "properties": {}},
        task_type=task_type,
    )
    TaskDefinition.objects.filter(pk=td.pk).update(latest_task_version=tdv)
    td.refresh_from_db()
    return td


def create_session(
    agent: AgentModel, av: AgentVersionModel,
) -> tuple[SessionModel, SessionVersionModel]:
    session = SessionModel.objects.create(name="test-session")
    sv = SessionVersionModel.objects.create(
        session=session, agent=agent, pinned_agent_version=av, version_number=1,
    )
    SessionModel.objects.filter(pk=session.pk).update(latest_session_version=sv)
    session.refresh_from_db()
    return session, sv


def create_completed_call(
    agent: AgentModel,
    task_def: TaskDefinition,
    session: SessionModel,
    sv: SessionVersionModel,
    carguments: dict | None = None,
) -> AgentTaskCall:
    tdv = task_def.latest_task_version
    ti = TaskInstance.objects.create(
        task_definition_version=tdv,
        session=session,
        session_version=sv,
        iarguments_json=carguments or {},
        requires_approval=False,
        max_subtask_errors=0,
        max_subtask_error_rate=0,
        limit_subtask_parallel_runs=0,
        limit_per_instance_parallel_runs=1,
        max_retries=0,
        retry_delay=10,
        retry_requires_approval=True,
    )
    call = AgentTaskCall.create(task_instance=ti, kwargs=carguments or {})
    AgentTaskCall.objects.filter(pk=call.pk).update(
        status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
    )
    call.refresh_from_db()
    return call


def create_data_collection(
    name: str,
    collection_type: str = "stream",
    sources: list | None = None,
    processor: dict | None = None,
    **overrides: Any,
) -> DataCollection:
    """Create a DataCollection with sensible defaults.

    Default processor is ``{"agent": "test-agent", "function": "test-func"}``
    unless overridden.  Callers can pass any DataCollection field as
    keyword argument.
    """
    defaults: dict[str, Any] = {
        "sources": sources if sources is not None else [],
        "processor": processor if processor is not None else
        {"agent": "test-agent", "function": "test-func"},
        "collection_type": collection_type,
    }
    defaults.update(overrides)
    return DataCollection.objects.create(name=name, **defaults)


def create_collection_item(
    collection: DataCollection,
    member: str,
    score: float = 1.0,
    value: dict | None = None,
    **overrides: Any,
) -> CollectionItem:
    """Create a CollectionItem with sensible defaults."""
    return CollectionItem.objects.create(
        collection=collection,
        member=member,
        score=score,
        value=value or {},
        **overrides,
    )
