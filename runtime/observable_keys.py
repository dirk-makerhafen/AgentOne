"""Write-side observable keys.

Every publishable key string the ORM emits is defined exactly once, here.
There is no key *derivation* from field introspection: each model has a small
explicit function, so adding a live list to the UI is a two-line change
(one key here, one ``ObservableList`` method on the read side).

Grammar
-------

    <Model>:<pk>                          one row
    <Model>.<field>:<id>                  a foreign-key scoped list
    <Model>.root                          rows with no parent_* set
    <key>@<field>:<value>                 explicit filter variant

Filter suffixes are appended in the order the call site passes them, and a
transition publishes **both** the old and the new value, otherwise a list can
only ever gain rows (archiving a session would never remove it from the active
sidebar).

The keys never contain ``[``, ``,`` or whitespace: htmx tokenises
``hx-trigger`` on those, and the suffix is used verbatim as an SSE event name.
"""
from __future__ import annotations

import itertools
import logging
from typing import Any

__all__ = ["observable_keys", "partial_row_keys"]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _val(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    value = getattr(value, "value", value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _uniq(values) -> list:
    seen = set()
    out = []
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _flag(current: bool, previous: dict | None, attname: str) -> list[bool]:
    """Current + previous value of a boolean filter, deduplicated."""
    prev = (previous or {}).get(attname, current)
    return _uniq([bool(current), bool(prev)])


def _ids(obj, previous: dict | None, field: str) -> list[int]:
    """Current + previous id of a foreign key, deduplicated."""
    attname = field if field.endswith("_id") else f"{field}_id"
    values = [getattr(obj, attname), (previous or {}).get(attname)]
    return _uniq(values)


def _filtered(keys: list[str], **dimensions: list) -> list[str]:
    """Base keys plus every combination of the given filter values.

    ``_filtered(["A.root"], is_archived=[False, True], project=[3])`` yields
    ``A.root``, ``A.root@is_archived:false``, ``A.root@is_archived:true``,
    ``A.root@project:3``, ``A.root@is_archived:false@project:3`` and
    ``A.root@is_archived:true@project:3``.
    """
    out = list(dict.fromkeys(keys))
    names = list(dimensions)
    if not names:
        return out
    for combo in itertools.product(*(dimensions[name] for name in names)):
        suffix = "".join(f"@{name}:{_val(value)}" for name, value in zip(names, combo))
        out.extend(key + suffix for key in keys)
    return out


def _relation_keys(model: str, obj, previous: dict | None, fields: tuple[str, ...],
                   *, filters: dict[str, list] | None = None) -> list[str]:
    keys: list[str] = []
    for field in fields:
        for value in _ids(obj, previous, field):
            relation = f"{model}.{field}:{value}"
            keys.append(relation)
            if filters:
                keys.extend(_filtered([relation], **filters))
    return keys


def _base(model: str, pk: int) -> list[str]:
    return [f"{model}:{pk}"] if pk is not None else []


# ---------------------------------------------------------------------------
# agents / skills / tasks
# ---------------------------------------------------------------------------

def _agent_keys(obj, previous=None):
    model = "AgentModel"
    archived = _flag(obj.is_archived, previous, "is_archived")
    keys = _base(model, obj.pk)
    keys.extend(_relation_keys(model, obj, previous,
                               ("parent_skill", "parent_agent", "parent_project"),
                               filters={"is_archived": archived}))
    if not (obj.parent_skill_id or obj.parent_agent_id or obj.parent_project_id):
        keys.extend(_filtered([f"{model}.root"], is_archived=archived))
    # _relation_keys already applied every filter dimension; wrapping the whole
    # list here would emit junk like AgentModel.root@is_archived:false@is_archived:false.
    return keys


def _agent_version_keys(obj, previous=None):
    return _base("AgentVersionModel", obj.pk) + _relation_keys(
        "AgentVersionModel", obj, previous, ("agent",))


def _skill_keys(obj, previous=None):
    model = "SkillModel"
    archived = _flag(obj.is_archived, previous, "is_archived")
    keys = _base(model, obj.pk)
    keys.extend(_relation_keys(model, obj, previous,
                               ("parent_agent", "parent_project", "parent_skill"),
                               filters={"is_archived": archived}))
    if not (obj.parent_agent_id or obj.parent_project_id or obj.parent_skill_id):
        keys.extend(_filtered([f"{model}.root"], is_archived=archived))
    # _relation_keys already applied every filter dimension; wrapping the whole
    # list here would emit junk like AgentModel.root@is_archived:false@is_archived:false.
    return keys


def _skill_version_keys(obj, previous=None):
    return _base("SkillModelVersion", obj.pk) + _relation_keys(
        "SkillModelVersion", obj, previous, ("skill",))


def _task_definition_keys(obj, previous=None):
    return _base("TaskDefinition", obj.pk) + _relation_keys(
        "TaskDefinition", obj, previous,
        ("parent_skill", "parent_agent", "parent_project", "parent_generation"))


def _task_definition_version_keys(obj, previous=None):
    return _base("TaskDefinitionVersion", obj.pk) + _relation_keys(
        "TaskDefinitionVersion", obj, previous, ("task_definition",))


# ---------------------------------------------------------------------------
# sessions / messages
# ---------------------------------------------------------------------------

def _session_keys(obj, previous=None):
    model = "SessionModel"
    archived = _flag(obj.is_archived, previous, "is_archived")
    active = _flag(obj.is_active, previous, "is_active")

    keys = _base(model, obj.pk)
    keys.extend(_relation_keys(model, obj, previous, ("parent_session",),
                               filters={"is_archived": archived}))
    keys.extend(_relation_keys(model, obj, previous, ("parent_project",),
                               filters={"is_archived": archived}))

    # Emit root keys for both sides of a reparent: moving a root under a parent
    # must remove it from the root sidebar, not just add it to the child list.
    was_root = (previous or {}).get("parent_session_id", obj.parent_session_id) is None
    if obj.parent_session_id is None or was_root:
        keys.extend(_filtered([f"{model}.root"], is_archived=archived))
        for project in _ids(obj, previous, "parent_project"):
            keys.extend(_filtered([f"{model}.root@project:{project}"],
                                  is_archived=archived))

    keys.extend(f"{model}@is_active:{_val(value)}" for value in active)
    return keys


def _session_version_keys(obj, previous=None):
    return _base("SessionVersionModel", obj.pk) + _relation_keys(
        "SessionVersionModel", obj, previous,
        ("session", "agent", "parent_session", "workspace"))


def _message_keys(obj, previous=None):
    return _base("Message", obj.pk) + _relation_keys(
        "Message", obj, previous, ("session", "session_version", "prev_message"))


def _message_part_keys(obj, previous=None):
    return _base("MessagePart", obj.pk) + _relation_keys(
        "MessagePart", obj, previous, ("message", "tool_call"))


def _query_keys(obj, previous=None):
    return _base("Query", obj.pk) + _relation_keys(
        "Query", obj, previous, ("session", "session_version", "trigger_message"))


def _query_message_keys(obj, previous=None):
    return _base("QueryMessage", obj.pk) + _relation_keys(
        "QueryMessage", obj, previous, ("query", "source_message"))


def _query_message_part_keys(obj, previous=None):
    return _base("QueryMessagePart", obj.pk) + _relation_keys(
        "QueryMessagePart", obj, previous, ("query_message", "source_message_part"))


def _response_keys(obj, previous=None):
    return _base("Response", obj.pk) + _relation_keys(
        "Response", obj, previous, ("query", "session", "session_version"))


def _query_template_version_keys(obj, previous=None):
    return _base("QueryTemplateVersion", obj.pk) + _relation_keys(
        "QueryTemplateVersion", obj, previous, ("content", "created_by_session"))


def _session_query_template_keys(obj, previous=None):
    return _base("SessionQueryTemplate", obj.pk) + _relation_keys(
        "SessionQueryTemplate", obj, previous, ("session",))


# ---------------------------------------------------------------------------
# task calls / runs
# ---------------------------------------------------------------------------

def _task_call_keys(obj, previous=None):
    keys = _base("AgentTaskCall", obj.pk) + _relation_keys(
        "AgentTaskCall", obj, previous,
        ("session", "session_version", "task_instance", "task_definition",
         "cronjob", "parent_taskrun"))
    # A descendant's change must invalidate every ancestor's rendered sub-call
    # tree.  Cards subscribe to their own ``AgentTaskCall:<pk>`` trigger, and
    # delegated sub-calls can live in another session, so publishing only the
    # descendant's own keys never reaches the parent chat.
    if getattr(obj, "parent_taskrun_id", None):
        try:
            ancestors = obj.get_ancestor_call_pks()
        except Exception:  # pylint: disable=broad-exception-caught
            # A transient DB error must not fail the write, but silently
            # dropping these keys leaves tool cards stale, so log it.
            log.exception("Could not resolve ancestor call keys for AgentTaskCall %s", obj.pk)
            ancestors = []
        keys.extend(f"AgentTaskCall:{pk}" for pk in ancestors)
        # The right-bar Calls panel subscribes per session.  A delegated child
        # session's calls must refresh the *parent* panel too, so publish the
        # ancestor sessions' keys (the call's own session key is already in
        # ``_relation_keys`` above).
        if ancestors:
            try:
                from server.models.tasks.agent_task_call import AgentTaskCall

                session_ids = (
                    AgentTaskCall.objects.filter(pk__in=ancestors)
                    .values_list("session_id", flat=True)
                    .distinct()
                )
                keys.extend(
                    f"AgentTaskCall.session:{sid}" for sid in session_ids if sid
                )
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception(
                    "Could not resolve ancestor session keys for AgentTaskCall %s",
                    obj.pk,
                )
    return keys


def _task_run_keys(obj, previous=None):
    return _base("AgentTaskRun", obj.pk) + _relation_keys(
        "AgentTaskRun", obj, previous,
        ("agent_task_call", "task_instance", "session", "session_version"))


def _task_instance_keys(obj, previous=None):
    return _base("TaskInstance", obj.pk) + _relation_keys(
        "TaskInstance", obj, previous,
        ("session", "session_version", "task_definition_version"))


# ---------------------------------------------------------------------------
# projects / workspaces / agents' neighbours
# ---------------------------------------------------------------------------

def _project_keys(obj, previous=None):
    return _base("Project", obj.pk) + ["Project.root"]


def _workspace_keys(obj, previous=None):
    model = "WorkspaceModel"
    keys = _base(model, obj.pk) + _relation_keys(model, obj, previous, ("parent_project",))
    if obj.parent_project_id is None:
        keys.append(f"{model}.root")
    return keys


def _cron_keys(obj, previous=None):
    model = "Cronjob"
    archived = _flag(obj.is_archived, previous, "is_archived")
    keys = _base(model, obj.pk)
    keys.extend(_relation_keys(model, obj, previous, ("agent",),
                               filters={"is_archived": archived}))
    keys.extend(_relation_keys(model, obj, previous, ("parent_project", "workspace"),
                               filters={"is_archived": archived}))
    if obj.parent_project_id is None:
        keys.extend(_filtered([f"{model}.root"], is_archived=archived))
    # _relation_keys already applied every filter dimension; wrapping the whole
    # list here would emit junk like AgentModel.root@is_archived:false@is_archived:false.
    return keys


def _collection_keys(obj, previous=None):
    model = "DataCollection"
    keys = _base(model, obj.pk) + _relation_keys(model, obj, previous, ("parent_project",))
    if obj.parent_project_id is None:
        keys.append(f"{model}.root")
    return keys


def _collection_item_keys(obj, previous=None):
    return _base("CollectionItem", obj.pk) + _relation_keys(
        "CollectionItem", obj, previous,
        ("collection", "source_call", "source_item", "dispatch_source_call"))


# ---------------------------------------------------------------------------
# work items / terminals / providers / misc
# ---------------------------------------------------------------------------

def _work_item_keys(obj, previous=None):
    from server.models.workitems.enums import WorkItemStatus

    model = "WorkItem"
    terminal_statuses = {_val(WorkItemStatus.DONE), _val(WorkItemStatus.CANCELLED)}
    status = _val(obj.status)
    prev_status = _val((previous or {}).get("status", obj.status))
    terminal = _uniq([status in terminal_statuses, prev_status in terminal_statuses])

    keys = _base(model, obj.pk)
    keys.extend(_relation_keys(model, obj, previous,
                               ("parent", "assigned_agent", "executor_session",
                                "root_task")))
    if obj.project_id is None:
        keys.extend(_filtered([f"{model}.root"], terminal=terminal))
    project_keys = [
        f"{model}.project:{value}" for value in _ids(obj, previous, "project")
    ]
    keys.extend(_filtered(project_keys, terminal=terminal))
    return keys


def _terminal_keys(obj, previous=None):
    return _base("TerminalSession", obj.pk) + _relation_keys(
        "TerminalSession", obj, previous, ("session", "workspace"))


def _provider_keys(obj, previous=None):
    return _base("ApiProvider", obj.pk) + ["ApiProvider.root"]


def _ai_model_keys(obj, previous=None):
    return _base("AiModel", obj.pk)


def _ai_model_offering_keys(obj, previous=None):
    return _base("AiModelOffering", obj.pk) + _relation_keys(
        "AiModelOffering", obj, previous, ("api_provider", "model"))


def _api_key_keys(obj, previous=None):
    return _base("ApiKey", obj.pk) + _relation_keys(
        "ApiKey", obj, previous, ("api_provider",))


def _debug_log_keys(obj, previous=None):
    return _base("DebugLogEntry", obj.pk) + _relation_keys(
        "DebugLogEntry", obj, previous, ("session",))


def _settings_keys(obj, previous=None):
    return _base("SettingsModel", obj.pk) + _relation_keys(
        "SettingsModel", obj, previous,
        ("aimodel", "task_prompt", "system_prompt", "session_bootstrap",
         "preferred_api_key"))


def _adhoc_tool_version_keys(obj, previous=None):
    return _base("AdhocToolVersion", obj.pk) + _relation_keys(
        "AdhocToolVersion", obj, previous, ("content", "created_by_session"))


def _session_adhoc_tool_keys(obj, previous=None):
    return _base("SessionAdhocTool", obj.pk) + _relation_keys(
        "SessionAdhocTool", obj, previous, ("session", "version"))


def _system_keys(obj, previous=None):
    return _base("System", obj.pk) + ["System.root"]


def _bare_pk(obj, previous=None):
    return _base(type(obj).__name__, obj.pk)


def partial_row_keys(instance) -> list[str]:
    """Keys for a deliberate partial publish of one row.

    Callers that suppress the normal ``save()`` publish (streaming token
    flushes, token-count corrections) use this instead of an inline
    ``f"Model:{pk}"`` string.  The model-wide key is intentionally omitted so a
    1 Hz token update cannot refetch every list that watches the bare model.
    """
    return _base(type(instance).__name__, instance.pk)


_BUILDERS = {
    "AdhocToolVersion": _adhoc_tool_version_keys,
    "AgentModel": _agent_keys,
    "AgentTaskCall": _task_call_keys,
    "AgentTaskRun": _task_run_keys,
    "AgentVersionModel": _agent_version_keys,
    "AiModel": _ai_model_keys,
    "AiModelOffering": _ai_model_offering_keys,
    "ApiKey": _api_key_keys,
    "ApiProvider": _provider_keys,
    "CollectionItem": _collection_item_keys,
    "Cronjob": _cron_keys,
    "DataCollection": _collection_keys,
    "DebugLogEntry": _debug_log_keys,
    "Message": _message_keys,
    "MessagePart": _message_part_keys,
    "Project": _project_keys,
    "Query": _query_keys,
    "QueryMessage": _query_message_keys,
    "QueryMessagePart": _query_message_part_keys,
    "QueryTemplateVersion": _query_template_version_keys,
    "Response": _response_keys,
    "SessionAdhocTool": _session_adhoc_tool_keys,
    "SessionModel": _session_keys,
    "SessionQueryTemplate": _session_query_template_keys,
    "SessionVersionModel": _session_version_keys,
    "SettingsModel": _settings_keys,
    "SkillModel": _skill_keys,
    "SkillModelVersion": _skill_version_keys,
    "System": _system_keys,
    "TaskDefinition": _task_definition_keys,
    "TaskDefinitionVersion": _task_definition_version_keys,
    "TaskInstance": _task_instance_keys,
    "TerminalSession": _terminal_keys,
    "WorkItem": _work_item_keys,
    "WorkspaceModel": _workspace_keys,
}


def observable_keys(instance, previous: dict | None = None) -> list[str]:
    """Return the explicit key list for one instance change.

    ``previous`` maps ``<field>_id`` / filter field attnames to their value
    *before* the write, so transitions publish both sides.
    """
    builder = _BUILDERS.get(type(instance).__name__, _bare_pk)
    keys = [type(instance).__name__, *builder(instance, previous)]
    return list(dict.fromkeys(keys))
