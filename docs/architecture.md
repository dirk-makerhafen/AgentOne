# Architecture

> **UI status (2026-11):** the only UI is `webui/` — Django templates + htmx + SSE, mounted at `/app/` (and `/` redirects to it). See [`ui-rewrite.md`](ui-rewrite.md) and [`observables-migration.md`](observables-migration.md).

## System overview

AgentOne is structured as a Django monolith with Celery for async task execution. The UI is server-rendered: `webui/` renders Django templates, htmx fetches independently cached components/fragments over HTTP, and a per-tab event socket (`/app/ws/events/`, watch registration via `POST /app/sse/watch`) forwards Redis pub/sub events so only components that rendered a key refetch.

```
┌──────────────────────────────────────────────────────────────┐
│                          BROWSER / HTTP CLIENT                 │
│  Browser (webui) ─────────── HTTP + WS ─────► Django ASGI      │
│  (Django templates + htmx,  /app/*, /app/ws/events/)           │
│                                                               │
│  REST API client ──────────── HTTP ────────► Django WSGI     │
│  (curl, scripts, CI)            /api/v1/*                     │
└──────────────────────────────────────────────────────────────┘
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

### Direct LLM call (side path)

The `llm_query` tool (task `call_llm_direct`, `.agentone/scripts/core/call_llm_direct.py`) runs a lightweight Input → LLM → result query on an ephemeral inactive session, reusing the `call_llm` pipeline. See [Core mechanisms](core-mechanisms.md#direct-llm-call-llm_query--call_llm_direct) for the full contract. The `template_execute` tool renders a session-private query template (`runtime/query_templates.py`) and dispatches it through the same path; the Templates right-panel tab does the same for human users.

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

## UI rendering (webui)

- Server-rendered Django templates with htmx component/fragment requests (`GET /app/c/...`, section sidebars, and feature fragments).
- Components carry observable keys and ETags; unchanged responses can return `204` so the client preserves DOM state.
- Live updates: per-tab WebSocket at `ws(/wss) /app/ws/events/` (see `webui/core/events.py`, `webui/static/webui/ws-events.js`) delivers event names from Redis pub/sub; the client syncs watched keys via `POST /app/sse/watch`.
- For details, see [`ui-rewrite.md`](ui-rewrite.md), [`observables-migration.md`](observables-migration.md), and [`htmx-sse.md`](htmx-sse.md).

### Rightbar assistant sessions

Every management page's rightbar chat is an `AgentOne` session (the Memory page
uses `memory-manage`). `webui/core/assistants.py` resolves one workspace per
page kind: a workspace detail page binds that workspace, a project detail page
binds the project's primary workspace, and everything else binds the single
**AgentOne home** workspace at `agentone_home()` (`~/.agentone`). The old
per-domain workspaces (`System agents`, `System skills`, `System cronjobs`,
`*_assistant_scope`) are no longer created; the legacy `AgentOne system` row is
renamed in place so existing chats keep their binding.

New assistant chats pin a one-time `SYSTEM_NOTICE` naming the page, the
subject and the expected work. `admin_tool` accepts explicit
`project_pk`/`project_name` and `workspace_pk`/`workspace_name` when the
session's inferred scope is not the intended target.

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
