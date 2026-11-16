"""Model -> read API registry, with explicit coverage.

Every concrete observable model is listed exactly once: either it has a
domain API (lists / values), or it is row-only (observed by primary key).
A coverage test asserts that no model is missing.
"""
from __future__ import annotations

from django.db.models import Model

from runtime.observable_queries.agents import (
    AgentObservables,
    AgentVersionObservables,
    SkillObservables,
    SkillVersionObservables,
)
from runtime.observable_queries.base import ObservableBase, RowObservables
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
    CollectionItemObservables,
    CollectionObservables,
    CronjobObservables,
    WorkItemObservables,
)

_APIS: dict[str, ObservableBase] = {
    "SessionModel": SessionObservables(),
    "Message": MessageObservables(),
    "Query": QueryObservables(),
    "Response": ResponseObservables(),
    "AgentTaskCall": TaskCallObservables(),
    "AgentModel": AgentObservables(),
    "AgentVersionModel": AgentVersionObservables(),
    "SkillModel": SkillObservables(),
    "SkillModelVersion": SkillVersionObservables(),
    "Cronjob": CronjobObservables(),
    "DataCollection": CollectionObservables(),
    "CollectionItem": CollectionItemObservables(),
    "WorkItem": WorkItemObservables(),
    "Project": ProjectObservables(),
    "WorkspaceModel": WorkspaceObservables(),
    "ApiProvider": ProviderObservables(),
    "AiModel": AiModelObservables(),
    "TerminalSession": TerminalObservables(),
}

#: Models whose UI is only ever addressed by primary key.
ROW_ONLY = frozenset({
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
})


def api_for(model: type[Model] | str) -> ObservableBase:
    name = model if isinstance(model, str) else model.__name__
    if name in _APIS:
        return _APIS[name]
    if name in ROW_ONLY:
        from django.apps import apps

        return RowObservables(apps.get_model("server", name))
    raise KeyError(f"{name} has no observable read API; add one in registry.py")
