# Models reference

All 28+ model classes, organized by domain.

## Inheritance structure

```
models.Model
  ├── BaseModel(DirtyFieldsMixin, abstract)    ← most models inherit this
  │     ├── created_at, updated_at, raw_data, fork_of, raw_data_reference
  │     │
  │     ├── AgentModel                         # Agent definition
  │     ├── AgentVersionModel                   # Immutable agent version
  │     ├── TaskDefinition                      # Task definition
  │     ├── TaskDefinitionVersion               # Immutable task version
  │     ├── TaskInstance                        # Session-bound task instance
  │     ├── AgentTaskCall                       # The "promise"
  │     ├── AgentTaskRun                        # The execution
  │     ├── SessionModel                        # Session record
  │     ├── SessionVersionModel                 # Immutable session version
  │     ├── Message                             # Chat message
  │     ├── MessagePart                         # Message content part
  │     ├── Query                               # LLM query
  │     ├── QueryMessage                        # Query message
  │     ├── QueryMessagePart                    # Query message part
  │     ├── Response                            # LLM response
  │     ├── SettingsModel                       # Agent settings (immutable)
  │     ├── System                              # Remote executor
  │     ├── DebugLogEntry                       # Debug event log
  │     ├── AiModel                             # AI model config
  │     ├── ApiKey                              # API key
  │     └── ApiProvider                         # API provider
  │
  ├── GenericContent                           # Content-addressed storage
  ├── Cronjob                                  # Scheduled cron jobs
  ├── HistoryLimitingRule                      # Tool usage limits
  ├── HistoryLimitingRule                      # Tool usage limits
  ├── Project                                  # Project grouping
  ├── SkillDefinition                          # Registered skill
  ├── SkillModel                               # Skill (no versioning)
  └── WorkspaceModel                           # Workspace
```

## BaseModel (abstract)

File: `server/models/base_model.py`

```python
class BaseModel(DirtyFieldsMixin, models.Model):
    class Meta:
        abstract = True
```

| Field | Type | Notes |
|---|---|---|
| `created_at` | `DateTimeField(auto_now_add, db_index)` | Set once on creation |
| `updated_at` | `DateTimeField(auto_now)` | Updated on every save |
| `raw_data` | `TextField(100MB)` | JSON blob storage (arbitrary model data) |
| `fork_of` | `FK(self, SET_NULL)` | Fork source for deduplication |
| `raw_data_reference` | `FK(self, SET_NULL)` | Shared data reference (copy-on-write) |

**`.data` property**: Parses `raw_data` as JSON (cached). Setter serializes dict to JSON.

**`save()`**: Auto-serializes `_data` to `raw_data`. Tracks dirty fields via `DirtyFieldsMixin` and only updates changed fields. Sets `updated_at`.

---

## Agents

### AgentModel

File: `server/models/agents/agent.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255, unique)` | Agent name |
| `latest_agent_version` | `FK(AgentVersionModel, SET_NULL)` | Pointer to current version |
| `parent_skill` | `FK(SkillModel, CASCADE)` | Parent skill (if agent is nested) |
| `parent_agent` | `FK(self, CASCADE)` | Parent agent (for subagent hierarchies) |
| `parent_project` | `FK(Project, CASCADE)` | Parent project |

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

### AgentVersionModel

File: `server/models/agents/agent_version.py`

| Field | Type | Notes |
|---|---|---|
| `agent` | `FK(AgentModel, CASCADE)` | Parent agent |
| `description` | `TextField(65500)` | |
| `extends_agent_names` | `JSONField(list)` | Inherited agent names |
| `extends_agent_versions` | `SortedManyToMany(self)` | Inherited version refs |
| `defined_skill_versions` | `M2M(SkillModelVersion)` | Skills defined here |
| `defined_task_versions` | `M2M(TaskDefinitionVersion)` | Tasks defined here |
| `defined_subagent_versions` | `M2M(self)` | Subagents defined here |
| `skill_versions` | `M2M(SkillModelVersion)` | Resolved (inherited) skills |
| `task_versions` | `M2M(TaskDefinitionVersion)` | Resolved tasks |
| `subagent_versions` | `M2M(self)` | Resolved subagents |
| `subagent_configs` | `JSONField(dict)` | Subagent metadata |
| `agent_settings` | `FK(SettingsModel, SET_NULL)` | Settings snapshot |
| `version_number` | `IntegerField` | Auto-incrementing |
| `commit` | `CharField(1024)` | Git commit hash |
| `hash` | `CharField(1024)` | Content hash |

**Unique**: `(agent, version_number)`

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

**Key methods**:
- `get_or_create_session(name, ...)` — Creates `SessionModel` + `SessionVersionModel`
- `resolve_setting(name)` — Walks inheritance chain to resolve settings (supports `+` merge for list fields)
- `tasks()` / `tools()` / `commands()` — Filter `task_versions` by `TaskType`
- `skills()` — Returns `skill_versions`

---

## Sessions

### SessionModel

File: `server/models/sessions/session.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255)` | Session name |
| `turn_count` | `IntegerField(default=0)` | User message count |
| `unattended_turn_count` | `IntegerField(default=0)` | Auto-turn count |
| `is_active` | `BooleanField(default=True)` | |
| `parent_session` | `FK(self, CASCADE)` | Parent session |
| `latest_session_version` | `FK(SessionVersionModel, CASCADE)` | Current version pointer |

**Properties**: `messages` (all Messages across versions), `queries` (all Queries across versions).

### SessionVersionModel

File: `server/models/sessions/session_version.py`

| Field | Type | Notes |
|---|---|---|
| `session` | `FK(SessionModel, CASCADE)` | Parent session |
| `agent` | `FK(AgentModel, CASCADE)` | Bound agent |
| `pinned_agent_version` | `FK(AgentVersionModel, CASCADE)` | Pinned agent version |
| `parent_session_version` | `FK(self, CASCADE)` | Parent version |
| `workspace` | `FK(WorkspaceModel, CASCADE)` | Bound workspace |
| `name` | `CharField(255)` | |
| `display_name` | `CharField(2048)` | |
| `description` | `TextField(65500)` | |
| `child_session_versions` | `M2M(self, symmetrical=False)` | Children |
| `session_settings` | `FK(SettingsModel, SET_NULL)` | Settings snapshot |
| `version_number` | `IntegerField(default=0)` | |

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

---

## Tasks

The task dispatch pipeline uses three layers: **TaskInstance** (session-bound template) → **AgentTaskCall** (the promise) → **AgentTaskRun** (the execution).

```
TaskDefinition              → mutable definition record
  └── TaskDefinitionVersion → immutable version with schema, type, mode
        └── TaskInstance    → bound to a session, overridable options
              └── AgentTaskCall → call-level state machine (status)
                    └── AgentTaskRun → run-level state machine (result)
```

### TaskDefinition

File: `server/models/tasks/task_definition.py`

| Field | Type | Notes |
|---|---|---|
| `parent_skill` | `FK(SkillModel, CASCADE)` | Owner skill (optional) |
| `parent_agent` | `FK(AgentModel, CASCADE)` | Owner agent (optional) |
| `parent_project` | `FK(Project, CASCADE)` | Owner project (optional) |
| `name` | `CharField(255)` | Task name |
| `group_name` | `CharField(255, default="")` | Group for wildcard matching |
| `latest_task_version` | `FK(TaskDefinitionVersion, SET_NULL)` | Current version |

**Unique**: `(parent_skill, parent_agent, parent_project, name)`

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

### TaskDefinitionVersion

File: `server/models/tasks/task_definition_version.py`

| Field | Type | Notes |
|---|---|---|
| `task_definition` | `FK(TaskDefinition, CASCADE)` | Parent definition |
| `description` | `TextField` | |
| `function_schema` | `JSONField` | JSON schema for arguments |
| `task_type` | `CharField(choices=TaskType)` | TASK / TOOL / COMMAND / WEBAPI / WEBVIEW |
| `task_execution_mode` | `CharField(choices=TaskExecutionMode)` | FUNCTION / SCRIPT / CHAIN / GROUP / CHORD / MAP |
| `requires_approval` | `BooleanField(default=False)` | Human-in-the-loop |
| `bound` | `BooleanField(default=False)` | Session passed as first arg |
| `function_name` | `CharField(255)` | Python function name |
| `path` | `CharField(1024)` | File path to script |
| `commit` | `CharField(1024)` | Git commit hash |
| `pipe_output_names` | `JSONField(list)` | Named pipe outputs |
| `child_tasks` | `SortedManyToMany(self)` | Sub-tasks for CHAIN/GROUP |

Plus execution constraints: `time_limit`, `max_subtask_errors`, `max_retries`, `retry_delay`, `priority`, etc.

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

### TaskInstance

File: `server/models/tasks/task_instance.py`

| Field | Type | Notes |
|---|---|---|
| `task_definition_version` | `FK(TaskDefinitionVersion, CASCADE)` | Linked definition |
| `session` | `FK(SessionModel, CASCADE)` | Owning session |
| `session_version` | `FK(SessionVersionModel, CASCADE)` | Owning version |
| `iarguments_json` | `JSONField(dict)` | Instance-level arguments |
| `is_approved` | `BooleanField(nullable)` | Approval state |
| `parent_instances` / `child_instances` | `M2M(self)` | CHAIN/GROUP nesting |
| `taskinstance_arg_references` | `M2M(self)` | Arg dependencies |
| `taskinstance_result_references` | `M2M(self)` | Result dependencies |

Plus overridable execution options (same as call/run).

**Immutable**.

### AgentTaskCall (the "promise")

File: `server/models/tasks/agent_task_call.py`

| Field | Type | Notes |
|---|---|---|
| `task_definition` | `FK(TaskDefinition, CASCADE)` | Denormalized definition |
| `task_definition_version` | `FK(TaskDefinitionVersion, CASCADE)` | Pinned version |
| `task_instance` | `FK(TaskInstance)` | Source instance |
| `session` | `FK(SessionModel, CASCADE)` | Owning session |
| `session_version` | `FK(SessionVersionModel, CASCADE)` | Owning version |
| `carguments_json` | `JSONField(dict)` | Call arguments |
| `parent_taskrun` | `FK(AgentTaskRun, CASCADE)` | Creating run |
| `taskcall_arg_references` | `M2M(self)` | Depends on these calls |
| `taskcall_result_run` | `FK(AgentTaskRun, SET_DEFAULT)` | Result run pointer |
| `status` | `CharField(choices=TaskCallStatus)` | NEW / WAITING / ACTIVE / HALTED / ENDED |
| `status_detail` | `CharField(choices=TaskCallStatusDetail)` | Granular detail (16 states) |
| `ended_at` | `DateTimeField` | When call ended |

Plus scheduling fields (`dont_start_before`, `dont_start_after`) and hook M2Ms.

**Status flow**: `NEW` → `WAITING_DEPENDENCY` → `WAITING_QUEUE` → `ACTIVE_QUEUED` → `ACTIVE_RUNNING` → `ENDED_SUCCESS` (or `ENDED_FAILURE_*` / `HALTED_*`).

**Immutable**.

### AgentTaskRun (the execution)

File: `server/models/tasks/agent_task_run.py`

| Field | Type | Notes |
|---|---|---|
| `agent_task_call` | `FK(AgentTaskCall, CASCADE)` | Parent call |
| `task_instance` | `FK(TaskInstance)` | Source instance |
| `task_definition_version` | `FK(TaskDefinitionVersion)` | Resolved version |
| `session_version` | `FK(SessionVersionModel)` | Owning version |
| `arguments_json` | `JSONField(dict)` | Resolved arguments |
| `taskrun_arg_references` | `M2M(AgentTaskRun)` | Arg dependency runs |
| `taskrun_result_references` | `M2M(AgentTaskCall)` | Result-produced calls |
| `status` | `CharField(choices=TaskRunStatus)` | NEW / QUEUED / ACTIVE / WAITING_RESULTTASKS / RATE_LIMITED / SUCCESS / FAILURE |
| `result_json` | `JSONField` | Serialized result |

**Status flow**: `NEW` → `QUEUED` → `ACTIVE` → `SUCCESS` (or `FAILURE`). When a task returns `AgentTaskCall` refs, enters `WAITING_RESULTTASKS` until child calls resolve.

**Immutable** — `save(allow=True)` required to update after creation.

---

## Data Collections

### DataCollection

File: `server/models/collections/data_collection.py`

Unified model for both streams (append-only) and ordered sets (mutable). Each collection declares its own data-flow configuration.

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255, unique)` | Collection name |
| `description` | `TextField` | Human-readable description |
| `collection_type` | `CharField(10)` | `"stream"` or `"set"` |
| `is_active` | `BooleanField(default=True)` | Inactive flows are skipped |
| `sources` | `JSONField(list)` | Array of source definitions |
| `processor` | `JSONField(dict)` | Agent+function that transforms items |
| `on_removed` | `JSONField(dict)` | Handler for set removals |
| `member_field` | `TextField` | Python eval expression for set member |
| `score_field` | `TextField` | Python eval expression for set score |
| `retroactive_on_source_change` | `IntegerField` | Max items to reprocess when sources change |
| `max_reprocess` | `IntegerField` | Max items to reprocess on processor update |

### CollectionItem

File: `server/models/collections/collection_item.py`

| Field | Type | Notes |
|---|---|---|
| `collection` | `FK(DataCollection, CASCADE)` | Parent collection |
| `source_call` | `FK(AgentTaskCall, SET_NULL)` | The processor call that produced this item |
| `member` | `CharField(1024)` | Unique ID within the collection |
| `score` | `FloatField` | Ordering value (auto timestamp or user-defined) |
| `value` | `JSONField(dict)` | Payload data |

**Unique**: `(collection, member)` — enforces dedup for sets, no-op for streams (auto-hash member)

---

## Messages

### Message

File: `server/models/message.py`

| Field | Type | Notes |
|---|---|---|
| `session_version` | `FK(SessionVersionModel, CASCADE)` | Owning version |
| `response` | `FK(Response, CASCADE, nullable)` | Source LLM response |
| `prev_message` | `FK(self, CASCADE, nullable)` | Previous message in chain |
| `role` | `CharField(choices=MessageRole)` | user / assistant / system / tool |
| `source` | `CharField(choices=MessageSource)` | Origin type |
| `hide_from_context` | `BooleanField(default=False)` | Exclude from LLM context |
| `pin_to_context` | `BooleanField(default=False)` | Always include |

**`add_part(type, content_type, content, ...)`**: Creates a `MessagePart` attached to this message.

### MessagePart

| Field | Type | Notes |
|---|---|---|
| `message` | `FK(Message, CASCADE)` | Parent message |
| `tokens` | `IntegerField(default=0)` | Token count |
| `type` | `EnumField(MessagePartType)` | REASONING / MESSAGE / TOOLCALL |
| `content` | `FK(GenericContent, SET_DEFAULT)` | Content data |
| `content_type` | `EnumField(MessageContentType)` | TEXT / IMAGE / JSON / TEMPLATE |
| `template_data` | `FK(GenericContent, SET_DEFAULT)` | Template data |
| `tool_call` | `OneToOneField(AgentTaskCall)` | Tool call reference |

---

## Queries & Responses

### Query

File: `server/models/queries/query.py`

| Field | Type | Notes |
|---|---|---|
| `apikey` | `FK(ApiKey, SET_NULL)` | Used API key |
| `session_version` | `FK(SessionVersionModel, CASCADE)` | Owning version |
| `trigger_message` | `FK(Message, CASCADE, nullable)` | Triggering message |
| `status` | `EnumField(QueryStatus)` | ACTIVE / WAITING / SUCCESS / FAILURE |
| `tags_token_usage` | `JSONField(dict)` | Tagged token breakdowns |
| `tokens` | `IntegerField` | Total token count |

**Relationship**: Each Query has one Response (OneToOneField).

### QueryMessage

| Field | Type | Notes |
|---|---|---|
| `query` | `FK(Query, CASCADE)` | Parent query |
| `source_message` | `FK(Message, SET_DEFAULT)` | Source message |
| `role` | `EnumField(MessageRole)` | user/assistant/system/tool |
| `content_prefix` | `FK(GenericContent, SET_DEFAULT)` | Prepend content |
| `content_postfix` | `FK(GenericContent, SET_DEFAULT)` | Append content |
| `tags_token_usage` | `JSONField(dict)` | Tagged token usage |
| `tokens` | `IntegerField` | Token count |

### QueryMessagePart

| Field | Type | Notes |
|---|---|---|
| `query_message` | `FK(QueryMessage, CASCADE)` | Parent |
| `source_message_part` | `FK(MessagePart, SET_DEFAULT)` | Source part |
| `content` | `FK(GenericContent, SET_DEFAULT)` | Content |
| `content_type` | `EnumField(MessageContentType)` | TEXT / IMAGE / JSON / TEMPLATE |
| `tags` | `JSONField(list)` | Tag labels |

### Response

File: `server/models/queries/response.py`

| Field | Type | Notes |
|---|---|---|
| `query` | `OneToOneField(Query, CASCADE)` | Parent query |
| `session_version` | `FK(SessionVersionModel, CASCADE)` | Owning version |
| `status` | `EnumField(ResponseStatus)` | ACTIVE / WAITING / SUCCESS / FAILURE |
| `prompt_tokens` | `IntegerField(default=0)` | |
| `completion_tokens` | `IntegerField(default=0)` | |
| `time_to_first_token` | `FloatField` | ms |
| `token_generation_time` | `FloatField` | ms |
| `total_time` | `FloatField` | ms |
| `reasoning_time` | `FloatField` | ms |
| `tool_calls` | `JSONField(list)` | Tool calls made |
| `content` | `TextField(500000)` | Response text |
| `reasoning` | `TextField(500000)` | Reasoning text |
| `finish_reason` | `CharField(5000)` | Stop reason |

**`save()`**: On success, recalibrates token estimates across related QueryMessage/QueryMessagePart instances using proportional correction.

---

## Providers (LLM configuration)

Three-tier hierarchy: `ApiProvider` → `AiModel` → `ApiKey`, each with independent rate limits.

### ApiProvider

File: `server/models/providers/api_provider.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(512)` | Provider name |
| `url` | `CharField(512)` | Base URL |
| `limit_parallel_calls` | `IntegerField(default=0)` | 0 = unlimited |

### AiModel

File: `server/models/providers/ai_model.py`

| Field | Type | Notes |
|---|---|---|
| `api_provider` | `FK(ApiProvider, CASCADE)` | Parent provider |
| `name` | `CharField(512)` | Model name |
| `family` | `CharField(512)` | Model family |
| `description` | `TextField(65000)` | |
| `enabled` | `BooleanField(default=True)` | |
| `context_length` | `IntegerField(default=1000000)` | Context window |
| `is_cloud` | `BooleanField(default=True)` | Cloud vs local |
| `vision` | `BooleanField(default=False)` | Vision support |
| `billion_parameters` | `FloatField(default=0)` | Model size |
| `max_prompt_tokens` | `IntegerField(default=1000000)` | |
| `max_response_tokens` | `IntegerField(default=1000000)` | |
| `limit_request_per_day` | `IntegerField(default=0)` | |
| `limit_request_per_minute` | `IntegerField(default=0)` | |
| `limit_tokens_per_day` | `IntegerField(default=0)` | |
| `limit_tokens_per_minute` | `IntegerField(default=0)` | |
| `limit_parallel_calls` | `IntegerField(default=0)` | |

**Properties**: `total_llm_queries`, `total_prompt_tokens`, `total_completion_tokens`.

**Methods**: `is_rate_limited()` (checks all limits), `requests_last_minute()`, `requests_today()`, `tokens_last_minute()`, `tokens_today()`, `active_call_count()`, `pending_calls()`.

### ApiKey

File: `server/models/providers/api_key.py`

| Field | Type | Notes |
|---|---|---|
| `api_provider` | `FK(ApiProvider, CASCADE)` | Parent provider |
| `comment` | `CharField(512)` | Human-readable label |
| `key` | `CharField(512)` | Key value |
| `enabled` | `BooleanField(default=True)` | |
| `limit_request_per_day` | `IntegerField(default=0)` | |
| `limit_request_per_minute` | `IntegerField(default=0)` | |
| `limit_tokens_per_day` | `IntegerField(default=0)` | |
| `limit_tokens_per_minute` | `IntegerField(default=0)` | |

Same rate-limiting methods as AiModel.

---

## Skills

### SkillModel

File: `server/models/skills/skill.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255)` | Skill name |
| `latest_skill_version` | `FK(SkillModelVersion, SET_NULL)` | Current version |
| `parent_agent` | `FK(AgentModel, CASCADE)` | Owner agent |
| `parent_project` | `FK(Project, CASCADE)` | Owner project |
| `parent_skill` | `FK(self, CASCADE)` | Parent skill |

### SkillModelVersion

File: `server/models/skills/skill_version.py`

| Field | Type | Notes |
|---|---|---|
| `skill` | `FK(SkillModel, CASCADE)` | Parent skill |
| `description` | `TextField(1024)` | |
| `commit` | `TextField(1024)` | Git hash |
| `path` | `CharField(255)` | File path |
| `version_number` | `IntegerField(default=0)` | |

### SkillDefinition

File: `server/models/skill_definition.py`

| Field | Type | Notes |
|---|---|---|
| `skill_slug` | `CharField(100, unique)` | Unique slug |
| `name` | `CharField(200)` | Display name |
| `description` | `TextField` | Capabilities |
| `tool_description` | `TextField(nullable)` | Tool description |
| `target_source` | `CharField(255, nullable)` | Module path |
| `requires_auth` | `BooleanField(default=False)` | Auth requirement |

---
## Other models

### GenericContent

File: `server/models/content.py`

Content-addressed storage using SHA-256 as primary key.

| Field | Type | Notes |
|---|---|---|
| `sha256` | `CharField(64, PK)` | Content hash |
| `content` | `TextField` | Raw content |
| `content_type` | `EnumField(ContentType)` | TEXT / IMAGE / JSON |
| `expires_at` | `DateTimeField(nullable)` | Expiry |

**Classmethods**: `from_text()`, `from_image()`, `from_data()` (JSON), `from_file()` — create or retrieve by hash.

### Project

File: `server/models/project.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255)` | Project name |
| `description` | `TextField(10000)` | |
| `path` | `CharField(255)` | Filesystem path |

### WorkspaceModel

File: `server/models/workspace.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255)` | Workspace name |
| `description` | `TextField(10000)` | |
| `path` | `CharField(255)` | Filesystem path |

### SettingsModel

File: `server/models/settings.py`

Comprehensive agent/session settings. All nullable — values inherit through the agent hierarchy.

| Field | Type | Notes |
|---|---|---|
| `aimodel` | `FK(AiModel, CASCADE)` | Model choice |
| `thinking` | `BooleanField` | Enable thinking tokens |
| `reasoning_effort` | `CharField(choices=ReasoningEffort)` | none / minimal / low / medium / high / xhigh |
| `precision` | `FloatField(choices=ResponseTemperature)` | 0.05 (precise) — 1.0 (experimental) |
| `max_retries` | `IntegerField` | |
| `max_turns` | `IntegerField` | |
| `scheduler_strategy` | `CharField(choices=TaskSchedulerStrategy)` | interrupt / queue / merge / parallel |
| `tool_call_syntax` | `CharField(choices)` | default / custom |
| `commandNames` / `taskNames` / `toolNames` / `skillNames` / `subagentNames` | `JSONField(list)` | Allow lists (wildcards) |
| `disallowed*Names` | `JSONField(list)` | Deny lists (wildcards) |
| `subagentResultDelivery` | `CharField(choices)` | passive / immediate |
| `extra_settings` | `JSONField` | Extensibility |
| `commit` | `TextField(1024)` | Git hash |

**Immutable** — `save()` raises `ValidationError` if `pk` is set.

### Cronjob

File: `server/models/cron.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255)` | |
| `description` | `TextField(10000)` | |
| `schedule` | `CharField(2048)` | Cron expression |
| `is_active` | `BooleanField(default=True)` | |
| `is_archived` | `BooleanField(default=False)` | Archived when removed from manifest |
| `agent` | `FK(AgentModel, CASCADE)` | Target agent |
| `parent_project` | `FK(Project, CASCADE, null)` | Project scoping for sidebar filtering |
| `session_mode` | `CharField(choices)` | new / existing |
| `session_name` | `CharField(255)` | |
| `message` | `FK(GenericContent, SET_DEFAULT)` | Message template |
| `function_type` | `CharField(choices)` | |
| `function_name` | `CharField(255)` | |
| `pipe_names` | `JSONField(list)` | Pipe outputs |
| `last_run_at` | `DateTimeField` | |
| `next_run_at` | `DateTimeField` | |
| `last_status` | `CharField(50)` | |
| `total_runs` | `IntegerField(default=0)` | |

Cron jobs can be defined via YAML frontmatter in `.agentone/cronjobs/<name>.md`
files at `.agentone/cronjobs/<name>.md` (loaded by `reload_all` /
`load_project_folder`) or created through the UI. File-based crons are
upserted by `(parent_project, name)`.

### System (remote executor)

File: `server/models/system.py`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(255, unique)` | |
| `description` | `TextField` | |
| `os` | `CharField(choices)` | LINUX / WINDOWS / OSX |
| `last_heartbeat` | `DateTimeField` | Last ping |
| `status` | `CharField(choices)` | online / offline / maintenance |
| `executor_mode` | `CharField(choices)` | LOCAL / HTTP / WEBSOCKET |
| `executor_url` | `URLField(1024)` | |
| `executor_api_key` | `CharField(255)` | |

### HistoryLimitingRule

File: `server/models/history_limit.py`

| Field | Type | Notes |
|---|---|---|
| `agent` | `FK(AgentModel, CASCADE)` | Target agent |
| `group_name` | `CharField(255, default="default")` | Tool group |
| `rule_name` | `CharField(255)` | Rule name |
| `description` | `TextField` | |
| `limit_success` | `PositiveIntegerField(nullable)` | |
| `limit_failed` | `PositiveIntegerField(nullable)` | |
| `limit_pending` | `PositiveIntegerField(nullable)` | |
| `limit_max` | `PositiveIntegerField(nullable)` | |

**Unique**: `(agent, group_name, rule_name)`

### DebugLogEntry

File: `server/models/debug_log_entry.py`

| Field | Type | Notes |
|---|---|---|
| `session` | `FK(SessionModel, CASCADE)` | Session |
| `event` | `CharField(64)` | Event name |
| `status` | `CharField(16)` | |

**Immutable**.

---

## Enum references

### TaskCallStatus (top-level call state)

`NEW` → `WAITING` → `ACTIVE` → `HALTED` → `ENDED`

### TaskCallStatusDetail (granular)

`NEW`, `WAITING_QUEUE`, `WAITING_RETRY`, `WAITING_DEPENDENCY`, `WAITING_SUBTASK`, `WAITING_RATELIMIT`, `ACTIVE_QUEUED`, `ACTIVE_RUNNING`, `HALTED_INPUT`, `HALTED_APPROVAL`, `HALTED_STAGNATED`, `HALTED_PAUSED`, `ENDED_SUCCESS`, `ENDED_FAILURE_EXCEPTION`, `ENDED_FAILURE_LOGIC`, `ENDED_CANCELLED`, `ENDED_STOPPED`

### TaskRunStatus (execution state)

`NEW` → `QUEUED` → `ACTIVE` → `WAITING_RESULTTASKS` → `SUCCESS` / `FAILURE` (with `RATE_LIMITED` as a side path)

### TaskType

`COMMAND`, `TASK`, `TOOL`, `WEBAPI`, `WEBVIEW`

### TaskExecutionMode

`FUNCTION` — single Python function call
`SCRIPT` — file-based script execution
`CHAIN` — sequential sub-tasks
`GROUP` — parallel sub-tasks
`CHORD` — barrier (all sub-tasks → callback)
`MAP` — map over inputs

### MessageRole

`USER`, `ASSISTANT`, `SYSTEM`, `TOOL`

### MessageContentType

`TEXT`, `IMAGE`, `JSON`, `TEMPLATE`

### MessagePartType

`REASONING`, `MESSAGE`, `TOOLCALL`

### HookType

`BEFORE_TOOL_CALL`, `AFTER_TOOL_CALL`, `BEFORE_LLM_RESPONSE`, `AFTER_LLM_RESPONSE`, `ON_TASK_START`, `ON_TASK_COMPLETE`, `ON_TASK_SUCCESS`, `ON_TASK_FAILURE`, `BEFORE_ENTRY`, `AFTER_ENTRY`

### SystemStatus, SystemOS, SystemConnectionMode

`ONLINE` / `OFFLINE` / `MAINTENANCE`; `LINUX` / `WINDOWS` / `OSX`; `LOCAL` / `HTTP` / `WEBSOCKET`
