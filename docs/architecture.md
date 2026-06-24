# Architecture

## System overview

AgentOne is structured as a Django monolith with Celery for async task execution and a custom WebSocket UI framework (pyHtmlGui). Data flows from the browser through Django Channels into a reactive Python view layer, which drives the agent runtime and Celery task pipeline.

```
┌──────────────────────────────────────────────────────────────┐
│                          BROWSER / HTTP CLIENT                 │
│  pyhtmlgui JS client ────── WebSocket ────► Django ASGI      │
│  (DOM sync, reconnect,        /ws                             │
│   ping, callbacks)                                            │
│                                                               │
│  REST API client ──────────── HTTP ────────► Django WSGI     │
│  (curl, scripts, CI)            /api/v1/*                     │
└──────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  API LAYER (api/)                           WSGI thread        │
│                                                                 │
│  DRF ViewSets + Serializers per domain:                        │
│  ├── auth/token/             JWT obtain + refresh               │
│  ├── health/                 DB + Redis check (no auth)         │
│  ├── me/                    Current user info                   │
│  ├── agents/                CRUD + resolved capabilities        │
│  │   └─ /{id}/commands/, /tasks/, /tools/, /skills/,           │
│  │      /subagents/, /versions/                                 │
│  ├── sessions/              CRUD + message + call + reset       │
│  ├── queries/               Read-only + cancel                  │
│  ├── collections/           CRUD + items + reprocess            │
│  ├── cron/                  CRUD + run                          │
│  ├── providers/             Read-only provider + model detail   │
│  ├── skills/                Read-only + versions                │
│  ├── projects/              CRUD                                │
│  ├── systems/               CRUD                                │
│  ├── workspaces/            CRUD                                │
│  ├── task-calls/            Read-only with nested runs          │
│  └── task-runs/             Read-only                           │
│                                                                 │
│  OpenAPI docs: /api/v1/schema/, /api/v1/docs/, /api/v1/redoc/  │
│  Auth: JWT (Bearer) + Session, stacked                          │
│  Search/filter/ordering across all viewsets                     │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  UI LAYER (ui/)                             WebSocket thread  │
│                                                                 │
│  UiApp (Observable data model)                                  │
│    ├── Agents, Sessions, Skills, DataCollections, Projects,     │
│    │   Workspaces (runtime wrapper collections)                  │
│    └── attach_observer/detach_observer                          │
│                                                                 │
│  UiAppView (root view)                                          │
│    ├── AppTitlebar                                              │
│    ├── RailView (desktop nav strip)                             │
│    ├── SidebarView (project selector + panel)                   │
│    │   └── SidebarPanel* (Chats, Agents, Skills, Cron, etc.)   │
│    ├── MainView (tab container)                                 │
│    │   ├── Chat (message list + composer + cards)               │
│    │   ├── SettingsView, AgentView, SkillView, ...              │
│    │   └── RightPanel (session/task/workspace/subagent detail)  │
│    └── Overlays (onboarding, mobile, dialog)                    │
│                                                                 │
│  pyHtmlGui framework (ui/lib/pyHtmlGui/)                        │
│    └── PyHtmlView.render() → Jinja2 → HTML → WebSocket         │
│    └── update() → replace_element(uid) → DOM patch             │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  DJANGO APP (server/)                       Main / WSGI thread │
│                                                                 │
│  Models (~30)                                                   │
│  ├── Agents: AgentModel → AgentVersionModel (immutable)        │
│  ├── Sessions: SessionModel → SessionVersionModel (immutable)  │
│  ├── Tasks: TaskDefinition → TaskDefinitionVersion              │
│  │   ├── TaskInstance (bound to session)                        │
│  │   ├── AgentTaskCall (the "promise")                          │
│  │   └── AgentTaskRun (the execution)                           │
│  ├── DataCollections: DataCollection → CollectionItem           │
│  ├── Messages: Message → MessagePart → GenericContent          │
│  ├── Skills: SkillModel → SkillModelVersion                     │
│  ├── Queries: Query → Response (LLM interaction)                │
│  ├── Providers: ApiProvider → AiModel → ApiKey                  │
│  ├── SettingsModel, Project, WorkspaceModel, Cronjob            │
│  └── BaseModel (abstract: created_at, updated_at, raw_data,    │
│                  fork_of, dirty-tracking, immutable save)       │
│                                                                 │
│  Admin: all models registered with django admin                 │
│  Prompts: system prompt template for agents                     │
│  Signals: auto-reload agent manifests on AgentModel save        │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  REGISTRY / LOADER (registry/)               On save / startup │
│                                                                 │
│  Loads YAML manifest files (.agentone/):                         │
│  ├── load_agent_manifest()    → agent.md fields                 │
│  ├── load_scripts_manifest() → scripts.md tool/group lists      │
│  ├── load_skill_manifest()   → skill.md definition              │
│  ├── load_cron_manifest()    → cron.md definition               │
│  ├── load_chain_entry()      → multi-step chain definitions     │
│  ├── load_python_entry()     → Python function introspection    │
│  └── load_project_folder()   → auto-discover from directories   │
│                                                                 │
│  install_repo.py: git-based runtime folder extraction           │
│  task_decorators.py: legacy @task/@tool/@command (dead)        │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  RUNTIME (runtime/)                         Celery workers      │
│                                                                 │
│  Wrapper collections (lazy-load + cache):                       │
│  ├── Agents   → Agent runtime (name resolution, allow/deny)    │
│  ├── Sessions → Session runtime (copy-on-write property access) │
│  ├── DataCollections → runtime query interface                   │
│  ├── Tasks    → BoundTask (session-bound task dispatch)         │
│  ├── Skills, Projects, Workspaces, Crons                         │
│                                                                 │
│  State machines (atomic SQL updates):                            │
│  ├── call_fsm.py → TaskCallStateMachine:                        │
│  │   NEW→WAITING_DEPENDENCY→WAITING_QUEUE→                      │
│  │   ACTIVE_QUEUED→ACTIVE_RUNNING→ENDED_SUCCESS                 │
│  │   →HALTED_APPROVAL (guardrail) →WAITING_QUEUE (approve)      │
│  │                              →ENDED_CANCELLED (deny)         │
│  └── run_fsm.py → TaskRunStateMachine:                          │
│      NEW→QUEUED→ACTIVE→SUCCESS/FAILURE                          │
│                                                                 │
│  Guardrails (runtime/guardrails.py):                             │
│  ├── check_shell_command() → sh-guard AST classifier            │
│  ├── check_python_command() → bandit + supplementary AST checks │
│  └── lint_shell_command() → pureshellcheck linting              │
│  All return GuardrailVerdict(action=allow/ask/deny, score, ...)  │
│                                                                 │
│  Rate limiter: 3-tier (provider→model→apikey) fail-fast         │
│  Runtime folder manager: versioned file extraction from git     │
└────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  CELERY TASKS (server/tasks/)                 Celery workers   │
│                                                                 │
│  tick_scheduler: runs every 5s via celery beat                  │
│    ├── AdvanceTaskCalls → process WAITING→QUEUED transitions    │
│    ├── AdvanceTaskRuns → process QUEUED→ACTIVE transitions      │
│    ├── _dispatch_data_flows → match completed calls to          │
│    │   DataCollection sources & dispatch processor tasks         │
│    └── _propagate_from_collections → cascade new items to       │
│        derived flows; detect removals & fire on_removed         │
│                                                                 │
│  heartbeat: runs every 2min, polls remote executors             │
│  task_dispatcher: AgentTaskCall → AgentTaskRun dispatch logic   │
└────────────────────────────────────────────────────────────────┘
```

## Core data flow

### User message → AI response cycle

```
1. User types message in Chat composer
2. SidebarPanelChat creates/completes Session → opens Chat tab
3. Composer sends message → Message model created
4. process_turn chain starts (Celery):
   a. build_llm_context → collects messages, tool schemas, system prompt
   b. call_llm → sends to LLM provider, creates Query/Response
   c. parse_llm_response → extracts tool calls, text, reasoning
   d. ingest_assistant_message → creates Message, links AgentTaskCalls
   e. decide_next_step → keeps processing or returns to user
5. Each step updates Observable → UiApp.notify_observers()
6. UI views update via WebSocket → browser DOM patches
```

### Task dispatch pipeline

```
BoundTask.delay(args)
  → TaskInstance.apply_async()
    → AgentTaskCall.create()           ← the "promise"
      → AgentTaskCall.apply_async()
        → CallScheduler._apply_async()
          → AgentTaskRun.create()      ← the execution attempt
            → RunScheduler._apply_async()
              → AgentTaskRun.apply()   ← actual Python execution
```

- `AgentTaskCall` tracks call-level status (NEW→WAITING→ACTIVE→ENDED, plus `HALTED_APPROVAL`)
- `AgentTaskRun` tracks run-level status (NEW→QUEUED→ACTIVE→SUCCESS/FAILURE)
- Dependencies: calls reference other calls via M2M → `WAITING_DEPENDENCY`
- Auto-await: if a task returns an `AgentTaskCall`, parent run enters `WAITING_RESULTTASKS`
- Guardrails: before dispatch, shell and Python commands are scanned by sh-guard/bandit; risky commands enter `HALTED_APPROVAL` for human decision

### Auto-await / result resolution

When a task returns a result containing `AgentTaskCall` references:

1. Run enters `WAITING_RESULTTASKS` state
2. The referenced calls are tracked via `taskrun_result_references`
3. On each tick, scheduler checks if all referenced calls are `ENDED_SUCCESS`
4. When all resolved, the parent run transitions to `SUCCESS`
5. Child calls' results become the parent run's result

This is the core mechanism behind `delegate_task` and subagent result delivery.

## Immutable versioned model pattern

Most models follow a **definition/version split**:

| Definition (mutable) | Version (immutable) |
|---|---|
| `AgentModel` | `AgentVersionModel` |
| `TaskDefinition` | `TaskDefinitionVersion` |
| `SessionModel` | `SessionVersionModel` |

- Definition records can be updated (name, parent pointers)
- Version records override `save()` to raise `ValidationError` on update
- Creating a new version increments `version_number` and updates the definition's `latest_*` pointer
- `fork_of` on `BaseModel` enables deduplication
- `raw_data` + `raw_data_reference` enable content-addressed JSON storage

## pyHtmlGui render pipeline

```python
# In any view:
self.update()                              # → triggers re-render
  → self.render()                          # → generates new HTML
    → Jinja2(TEMPLATE_STR, {"pyview": self})  # → server-side render
      → wraps in <DOM_ELEMENT id="uid">       # → scoped wrapper
        → pyhtmlgui.replace_element(uid, html) # → WebSocket call
          → document.getElementById(uid).outerHTML = html  # → DOM patch
```

- Views observe `Observable` subjects via `attach_observer()`
- On `notify_observers()`, all attached views call `update()`
- `QuerySetView` is lazy: children created only when visible, destroyed on hide
- `MultiQuerySetView` merges multiple querysets into one sorted list (e.g., chat timeline)

## WebSocket protocol

The browser establishes a single WebSocket connection at `/ws`.

**Client → Server:**
```json
{"call": true, "name": "pyview.methodName", "args": [...]}
```

**Server → Client (DOM updates):**
```json
{"call": true, "name": "pyhtmlgui.replace_element", "args": [uid, html]}
```

**Server → Client (response):**
```json
{"return": true, "value": ...}
```

## Rate limiting

Three tiers checked in order (fail-fast):

1. **Provider level** — `limit_parallel_calls` on `ApiProvider`
2. **Model level** — `limit_request_per_day/min`, `limit_tokens_per_day/min`, `limit_parallel_calls` on `AiModel`
3. **API key level** — `limit_request_per_day/min`, `limit_tokens_per_day/min` on `ApiKey`

`RateLimitChecker` in `runtime/rate_limiter.py` uses Redis counters with TTLs for rolling windows and a semaphore pattern for parallel call limits.

## Data flows (streams / ordered sets)

Data flows replace the legacy named-pipe system with a **collection-based** model.

### Collections

Two collection types on the `DataCollection` model:

| Type | Behaviour | Member | Score |
|---|---|---|---|
| **Stream** | Append-only, auto-hashdedup | SHA-256 of content+timestamp | Auto = `time.time()` |
| **Ordered Set** | Mutable (add/remove), dedup via `(collection, member)` unique | User-defined Python `eval()` expression | User-defined Python `eval()` expression |

Each collection is self-contained: it declares its **sources** (where input comes from), a **processor** (agent+function that transforms input into items), and optional **on_removed** handler for sets.

### Source types

| Type | Meaning |
|---|---|
| `query` | Match `AgentTaskCall` records by project/agent/session/function glob patterns |
| `stream` | Source from another stream's items |
| `set` | Source from another set's items |

### Dispatch flow

```
1. AgentTaskCall completes (ENDED_SUCCESS)
2. tick_scheduler._dispatch_data_flows():
     For each active DataCollection with query-type sources:
       Match recent completed calls → first match per flow per tick
       → _dispatch_processor(flow, call)
         → creates TaskInstance + AgentTaskCall for processor function
         → creates CollectionItem via update_or_create
3. tick_scheduler._propagate_from_collections():
     New items from any collection:
       → for each derived flow that sources from that collection
         → _dispatch_processor(derived_flow, item.source_call)
     Sets: detect removals by comparing current vs previous-tick member set
       → delete removed CollectionItems
       → fire _trigger_on_removed(flow, removed_source_calls)
```

### YAML definition

Defined in `.agentone/streams/*.md` and `.agentone/sets/*.md`:

```yaml
---
name: health_events
sources:
  - type: query
    agent: [collector]
    function: [check_health]
processor:
  agent: reporter
  function: parse_event
member_field: result.service     # sets only
score_field: result.priority     # sets only
on_removed:                     # sets only
  agent: reporter
  function: alert_removed
---
```

## API layer

The REST API (`api/`) provides HTTP access to core AgentOne abstractions using Django REST Framework, JWT authentication (simplejwt), and OpenAPI documentation (drf-spectacular).

All viewsets expose runtime-resolved data (e.g., inherited agent capabilities via the version chain, session settings via copy-on-write) rather than raw database rows. This ensures API consumers see the same resolved state as the WebSocket UI.

| Component | Technology |
|---|---|
| Framework | Django REST Framework (DRF) |
| Auth | `rest_framework_simplejwt` (JWT Bearer) + Session auth stacked |
| Docs | drf-spectacular (OpenAPI 3.0), Swagger UI, ReDoc |
| Filtering | django-filter (exact match), DRF SearchFilter (full-text), OrderingFilter |
| Pagination | PageNumberPagination (default page_size=10) |

### Endpoint index

| Prefix | Access | Details |
|---|---|---|
| `POST /api/v1/auth/token/` | None | JWT obtain (`username` + `password`) |
| `POST /api/v1/auth/token/refresh/` | None | JWT refresh |
| `GET /api/v1/health/` | None | DB + Redis connectivity check |
| `GET /api/v1/me/` | Authenticated | Current user (id, username, email, is_staff, is_superuser) |
| `/api/v1/agents/` | Authenticated | CRUD + `/commands/`, `/tasks/`, `/tools/`, `/skills/`, `/subagents/`, `/versions/` |
| `/api/v1/sessions/` | Authenticated | CRUD + `/message/`, `/messages/`, `/call/{task_name}/`, `/reset/` |
| `/api/v1/queries/` | Authenticated | Read-only list/detail + `/cancel/` |
| `/api/v1/collections/` | Authenticated | CRUD + `/items/`, `/reprocess/` |
| `/api/v1/cron/` | Authenticated | CRUD + `/run/` |
| `/api/v1/providers/` | Authenticated | Read-only list/detail |
| `/api/v1/models/` | Authenticated | Read-only list/detail |
| `/api/v1/skills/` | Authenticated | Read-only + `/versions/` |
| `/api/v1/projects/` | Authenticated | CRUD |
| `/api/v1/systems/` | Authenticated | CRUD |
| `/api/v1/workspaces/` | Authenticated | CRUD |
| `/api/v1/task-calls/` | Authenticated | Read-only with nested task runs |
| `/api/v1/task-calls/{id}/approve/` | Authenticated | Approve a HALTED_APPROVAL call → WAITING_QUEUE |
| `/api/v1/task-calls/{id}/deny/` | Authenticated | Deny a HALTED_APPROVAL call → ENDED_CANCELLED |
| `/api/v1/task-runs/` | Authenticated | Read-only |

OpenAPI schema at `GET /api/v1/schema/`, Swagger UI at `/api/v1/docs/`, ReDoc at `/api/v1/redoc/`.

---

**See also:** [User guide](user-guide.md) · [Core mechanisms](core-mechanisms.md) · [Development guide](development.md) · [Manifest format](manifest-format.md)

## Configuration sources
