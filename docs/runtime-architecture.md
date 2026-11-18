# Runtime Architecture — AgentOne

> **What this document is**: A technical deep-dive into how AgentOne executes
> agent conversations — task dispatch, state machines, LLM routing, error
> recovery, and rate limiting. It is the living specification for the runtime
> subsystem.

**Date**: 2026-11-17

---

## Table of Contents

1. [High-level Overview](#1-high-level-overview)
2. [Core Models & Relationships](#2-core-models--relationships)
3. [API Surface](#3-api-surface)
4. [Execution Pipeline](#4-execution-pipeline)
5. [State Machines](#5-state-machines)
6. [LLM Error Classification & Recovery](#6-llm-error-classification--recovery)
7. [Rate Limiting & Capacity Management](#7-rate-limiting--capacity-management)
8. [Model Switching](#8-model-switching)
9. [Data Storage Layout](#9-data-storage-layout)
10. [Integration Points](#10-integration-points)
11. [Key Architectural Decisions](#11-key-architectural-decisions)

---

## 1. High-level Overview

AgentOne is a **Django + Celery + SSE** application that manages agent sessions,
task definitions, and their execution. The core loop works like this:

1. A **user** sends a message through the web UI (htmx + SSE).
2. The **session** routes it to the appropriate **agent** configuration.
3. The agent's tasks (slash commands, tool calls, chain groups) are scheduled as
   **AgentTaskCall** instances.
4. The **CallScheduler** (Redis-backed) picks up calls, creates
   **AgentTaskRun** instances, and dispatches them to Celery workers via
   `run_runtime`.
5. Celery workers execute the run — for LLM calls, that means the
   `call_llm_direct` task which uses litellm to route to providers.
6. Results propagate back through run → call → session, with SSE events
   pushing state updates to the UI in real time.

**Key files**:

| File | Role |
|---|---|
| `runtime/session/session.py` | Session class: orchestrates agent loop, model selection, approval flow |
| `runtime/session/agent_executor.py` | Runs agent turns (slash commands, tool calls, chain logic) |
| `runtime/tasks/call_scheduler.py` | CallScheduler: creates calls, tracks dependencies, triggers LLM calls |
| `runtime/tasks/run_scheduler.py` | RunScheduler: manages AgentTaskRun lifecycle, result reference tracking |
| `runtime/tasks/call_fsm.py` | TaskCallStateMachine: atomic transitions for AgentTaskCall |
| `runtime/tasks/run_fsm.py` | TaskRunStateMachine: atomic transitions for AgentTaskRun |
| `runtime/tasks/run_runtime.py` | run_runtime._apply_async: Celery-side task run execution |
| `runtime/llm_errors.py` | classify_llm_error: classifies LLM exceptions into recovery paths |
| `runtime/rate_limiter.py` | AgentRateLimiter: multi-provider rate limiting with backoff |
| `runtime/session/aimodel_picker.py` | Model selection helpers: groups, siblings, health-aware picking |
| `server/models/tasks/agent_task_call.py` | AgentTaskCall model — the call-level state machine |
| `server/models/tasks/agent_task_run.py` | AgentTaskRun model — the execution attempt |
| `server/models/agents/agent.py` | Agent model — agent configuration, tools, task definitions |
| `server/models/providers/ai_model.py` | AiModel model — LLM model metadata, provider binding, health state |

---

## 2. Core Models & Relationships

### AgentTaskCall

The **AgentTaskCall** represents one scheduled invocation of a task within a
session. It carries the execution state machine.

**Key fields**:
- `session` — the AgentSession this call belongs to
- `agent` — the Agent whose task is being called
- `task` — the TaskDefinition being invoked
- `status` / `status_detail` — two-level state (e.g. `ACTIVE` → `ACTIVE_RUNNING`)
- `retry_count` / `max_retries` — retry budget
- `requires_approval` / `is_approved` — guardrail for user-confirmed actions
- `argument_task_calls` — reference to calls whose outputs are this call's inputs
- `rev_taskrun_result_references` — reverse FK: taskruns whose outputs feed
  into these calls
- `taskcall_result_run` — the AgentTaskRun that produced this call's result
- `session_root_task` — tracks the original root task (for cancellation propagation)

**State machine** (detailed in Section 5):

```
NEW → WAITING_DEPENDENCY → (HALTED_APPROVAL | WAITING_QUEUE)
                    → ACTIVE_QUEUED → ACTIVE_RUNNING
                                           ↓
                              WAITING_SUBTASKS_OR_HOOKS → ENDED_SUCCESS
                              WAITING_RETRY → retry loop
                              ENDED_FAILURE_EXCEPTION
                              ENDED_CANCELLED / ENDED_STOPPED
WAITING_RATELIMIT (rate-limited capacity path)
```

### AgentTaskRun

The **AgentTaskRun** represents one execution attempt of a task. A call can
have multiple runs (retries).

**Key fields**:
- `agent_task_call` — parent call
- `task` — task definition being executed
- `status` — NEW, QUEUED, ACTIVE, WAITING_RESULTTASKS, RATE_LIMITED, SUCCESS, FAILURE
- `result` — JSON result from execution
- `error` — error message on failure
- `agent_instance` — the Agent instance (for tool/chain execution context)
- `session` / `session_instance` — session context

### AgentSession

Represents a conversation or automation run.

**Key fields**:
- `user` / `agent` / `project` / `workspace` — scope resolution
- `current_model` — user-selected AI model (AiModel FK)
- `is_active` — session lifecycle flag
- `message_count` — running count
- `turn_count` — agent loop turns
- `context_items` — JSON list of system prompt items
- `stop_after` / `step_limit` — max step limits

**Subsessions** (AgentSession via FK `parent_session`) represent child
conversations spawned from parent sessions — tool calls, delegate tasks, etc.

### Agent

Agent configuration: tools, tasks, slash commands, chain rules.

**Key fields**:
- `name`, `display_name`, `description`
- `session_root_task` — initial task to execute
- `max_steps` — step limit per session
- `tools` — JSON tool definitions
- `system_prompt` — Jinja2 template
- `agent_prompt`, `context_items`, `stop_prompt` — message templates

### TaskDefinition

Reusable task templates.

**Key fields**:
- `name`, `agent` — ownership
- `execution_mode` — FUNCTION, SCRIPT, CHAIN, GROUP, MAP
- `scheduler_strategy` — INTERRUPT, QUEUE, MERGE, PARALLEL
- `task_type` — COMMAND, TASK, TOOL, WEBAPI, WEBVIEW
- `code`, `arguments`, `arguments_mapping` — execution definition
- `argument_mapping` — links task outputs to other tasks' inputs
- `slash_command` — flags command tasks (e.g. /stop, /retry)
- `stop_after` — execution limit

### AiModel

LLM model metadata with health tracking.

**Key fields**:
- `name` — canonical model name (e.g. "gpt-4o")
- `api_provider` — FK to ApiProvider (e.g. "OpenAI", "Anthropic")
- `enabled` — whether the model is available
- `model_health` — HealthStatus enum (HEALTHY, DEGRADED, RATE_LIMITED,
  UNAVAILABLE, AUTH_ERROR, CONFIG_ERROR)
- `model_health_updated_at` — when health was last updated
- `model_error_count` — error counter for health decay
- `backoff_until` — backoff timestamp (for DEGRADED/RATE_LIMITED)
- `model_name` — provider-side model identifier
- `default_api_key` — fallback key (can be set even without provider key)

### ApiProvider

LLM provider configuration (OpenAI, Anthropic, Vertex AI, etc.).

**Key fields**:
- `name`, `description`
- `api_key` — stored API key (encrypted)
- `default_api_key` — explicit default key for any model
- `enabled` — whether the provider is active
- `provider_settings` — JSON provider-specific settings
- `api_base_url` — custom base URL (for proxies, local models)

### RateLimitBucket (model: `RateLimitBucket`)

Per-provider per-model rate limiting state stored in Redis (backed by a model
row for persistence).

**Key fields**:
- `provider` — provider name
- `model` — model name
- `last_request_at` — timestamp of last request
- `remaining` — remaining capacity
- `reset_at` — when capacity resets

### AiProviderRateLimit (model: `AiProviderRateLimit`)

Persistent rate limit state with multi-key support.

**Key fields**:
- `api_provider` — FK to ApiProvider
- `model_name` — model identifier
- `key_name` — specific API key (for per-key limits)
- `rate_limit_remaining` — remaining requests
- `rate_limit_reset` — reset timestamp
- `is_rate_limited` — current rate limit flag

---

## 3. API Surface

### Django URLs

| URL Pattern | View | Purpose |
|---|---|---|
| `/` | `home` | Dashboard / sessions list |
| `/sessions/<pk>/` | `session_detail` | Session view with chat |
| `/sessions/<pk>/chat/` | `session_chat` | Chat area (htmx partial) |
| `/sessions/<pk>/messages/` | `session_messages` | Message list |
| `/sessions/<pk>/tasks/` | `session_tasks` | Task tree view |
| `/sessions/<pk>/stop/` | `session_stop` | Stop session |
| `/sessions/<pk>/approve/` | `session_approve` | Approve task call |
| `/sessions/<pk>/deny/` | `session_deny` | Deny task call |
| `/sessions/<pk>/retry/` | `session_retry` | Retry failed call |
| `/sessions/<pk>/resume/` | `session_resume` | Resume paused session |
| `/sessions/<pk>/export/` | `session_export` | Export session |
| `/api/session/<int:pk>/` | SessionAPI | REST session detail |
| `/api/session/<int:pk>/messages/` | SessionMessagesAPI | REST messages |
| `/api/session/<int:pk>/agent-tasks/` | SessionTaskRunsAPI | REST task runs |
| `/sse/session/<int:pk>/` | session_sse | SSE stream |
| `/tasks/run/<int:pk>/` | `run_detail` | Run detail view |
| `/tasks/run/<int:pk>/output/` | `run_output` | Run output |

### REST API (Session API)

- `GET /api/session/<pk>/` — Session detail with nested tasks, calls, runs
- `GET /api/session/<pk>/messages/` — Paginated messages list
- `GET /api/session/<pk>/agent-tasks/` — Task runs for the session
- `POST /api/session/<pk>/approve/` — Approve pending call
- `POST /api/session/<pk>/deny/` — Deny pending call
- `POST /api/session/<pk>/retry/` — Retry failed call

### SSE Events

The SSE endpoint (`/sse/session/<pk>/`) pushes real-time events:

| Event | Payload | Trigger |
|---|---|---|
| `session_update` | Session metadata | Session state changes |
| `message_new` | Message object | New user or agent message |
| `task_call_update` | TaskCall with status changes | FSM transitions |
| `task_run_update` | TaskRun with status changes | Run lifecycle changes |
| `approval_card` | Approval request data | requires_approval=True |
| `error` | Error message | Execution errors |

---

## 4. Execution Pipeline

### 4.1 Session Turn Flow

```
User sends message
    │
    ▼
Session.ingest_user_message(user_message)
    │  Updates AgentMessage, persists
    │  Calls session.process_turn()
    ▼
Session.process_turn()
    │  Determines task:
    │  - slash_command (if message starts with /)
    │  - agent_response (else, run agent loop)
    │
    ├─> _handle_slash_command(command)
    │       └─> CallScheduler._apply_async(slash_command_task)
    │
    └─> run_agent_loop()
            │  Uses agent.session_root_task as starting point
            │  Runs in a loop up to max_steps
            ▼
            CallScheduler._apply_async(root_task)
```

### 4.2 CallScheduler — Task Call Creation

The **CallScheduler** (in `call_scheduler.py`) is the bridge between the
session's Python code and the persistent task call system.

```
CallScheduler._apply_async(task)
    │
    ├─ 1. Create AgentTaskCall with status=NEW
    │
    ├─ 2. Call enter_dependency_wait() → WAITING_DEPENDENCY
    │
    ├─ 3. Resolve argument_task_calls:
    │      For each task whose output is needed as input:
    │      - Check if argument calls have already ended
    │      - If not: wait (the call stays in WAITING_DEPENDENCY)
    │
    ├─ 4. Once all dependencies resolved:
    │      - If requires_approval: request_approval() → HALTED_APPROVAL
    │      - Else: enqueue_after_dependencies() → WAITING_QUEUE
    │
    └─ 5. CallScheduler tick picks it up from WAITING_QUEUE
```

### 4.3 CallScheduler — Task Call Dispatch (Tick)

The CallScheduler runs on a Redis-backed tick (every 5 seconds from Celery beat).

```
CallScheduler.tick()
    │
    ├─ Pick up WAITING_QUEUE calls
    │
    ├─ CallScheduler._pick_up_call(call)
    │     │
    │     ├─ 1. transition pick_up() → ACTIVE_QUEUED
    │     │
    │     ├─ 2. Check if call's session_root_task was cancelled/stopped
    │     │
    │     ├─ 3. RunScheduler._apply_async(taskrun_id) — spawns Celery task
    │     │
    │     └─ 4. TaskCallStateMachine.start_running() → ACTIVE_RUNNING
    │            (paired with run transition, atomic rollback on race)
```

### 4.4 RunScheduler — Task Run Execution

```
RunScheduler._apply_async(taskrun_id)
    │
    ├─ 1. TaskRunStateMachine.start(taskrun_id) → ACTIVE
    │
    ├─ 2. TaskCallStateMachine.start_running(call_id) → ACTIVE_RUNNING
    │       (rollback to QUEUED if race condition)
    │
    ├─ 3. taskrun.apply()  ← runs the actual task code
    │       │
    │       ├─ FUNCTION → calls the registered function
    │       ├─ SCRIPT → executes the script
    │       ├─ CHAIN → runs sequential sub-tasks
    │       ├─ GROUP → runs parallel sub-tasks
    │       └─ TOOL → delegates to tool executor
    │
    │       Result: status in {SUCCESS, FAILURE, RATE_LIMITED, WAITING_RESULTTASKS}
    │
    ├─ 4. Handle RATE_LIMITED:
    │       TaskCallStateMachine.rate_limit() → WAITING_RATELIMIT
    │       (no retry budget consumed)
    │
    ├─ 5. Handle WAITING_RESULTTASKS:
    │       Check if referenced calls still pending
    │       - Yes: stay in WAITING_SUBTASKS_OR_HOOKS
    │       - No: resolve via all_taskrun_result_references_ended()
    │
    └─ 6. Handle SUCCESS/FAILURE:
            CallScheduler.on_taskrun_ended(taskrun_id, status)
```

### 4.5 CallScheduler — Post-Run Handling

```
CallScheduler.on_taskrun_ended(taskrun_id, status)
    │
    ├─ On FAILURE:
    │     │
    │     ├─ 1. Check if run produced sub-calls (argument_task_calls)
    │     │
    │     ├─ 2. If yes: check if any sub-call is still running
    │     │       - Yes: wait (stay in WAITING_SUBTASKS_OR_HOOKS)
    │     │       - No: schedule retry or fail
    │     │
    │     ├─ 3. If no sub-calls:
    │     │       - retry_count < max_retries: schedule_retry() → WAITING_RETRY
    │     │       - Else: fail() → ENDED_FAILURE_EXCEPTION
    │     │
    │     └─ 4. Model switch on specific errors:
    │           - If 400 config error: mark model UNAVAILABLE
    │           - If 401/403 auth: mark model AUTH_ERROR
    │           - If rate limited: mark model RATE_LIMITED
    │           - If model not found: mark model UNAVAILABLE
    │
    └─ On SUCCESS:
          │
          ├─ 1. Check if model was switched during this run
          │
          ├─ 2. Run hooks (post-processing, logging)
          │
          ├─ 3. Check if hooks produced sub-calls
          │       - Yes: stay in WAITING_SUBTASKS_OR_HOOKS
          │       - No: succeed() → ENDED_SUCCESS
          │
          └─ 4. Propagate result up the call chain
```

---

## 5. State Machines

### 5.1 AgentTaskCall FSM

The task call FSM is defined in `runtime/tasks/call_fsm.py`. All transitions
are **atomic** (single UPDATE statement with `WHERE` clause matching from-state).

**Valid transitions**:

```
NEW                           → WAITING_DEPENDENCY
WAITING_RETRY                 → WAITING_DEPENDENCY

WAITING_DEPENDENCY            → HALTED_APPROVAL     (requires_approval=True, not approved)
WAITING_DEPENDENCY            → WAITING_QUEUE       (approved or no approval needed)

HALTED_APPROVAL               → WAITING_QUEUE       (user approved)
HALTED_APPROVAL               → ENDED_CANCELLED     (user denied)

WAITING_QUEUE                 → ACTIVE_QUEUED       (scheduler picks up)

ACTIVE_QUEUED                 → WAITING_QUEUE       (recovery: Celery message lost)
ACTIVE_QUEUED                 → ACTIVE_RUNNING      (run starts)
ACTIVE_QUEUED                 → ENDED_CANCELLED     (cancelled before run)
ACTIVE_QUEUED                 → ENDED_STOPPED       (stopped before run)
ACTIVE_QUEUED                 → ENDED_FAILURE_EXCEPTION  (no runnable task in scope)

ACTIVE_RUNNING                → WAITING_SUBTASKS_OR_HOOKS  (run produced result, hooks pending)
ACTIVE_RUNNING                → ENDED_SUCCESS              (run succeeded, no hooks)
ACTIVE_RUNNING                → WAITING_RETRY              (run failed, retry available)
ACTIVE_RUNNING                → ENDED_FAILURE_EXCEPTION    (run failed, no retries)
ACTIVE_RUNNING                → WAITING_RATELIMIT          (rate limited)

WAITING_SUBTASKS_OR_HOOKS     → WAITING_SUBTASKS_OR_HOOKS  (stay, still waiting)
WAITING_SUBTASKS_OR_HOOKS     → ENDED_SUCCESS              (all resolved)
WAITING_SUBTASKS_OR_HOOKS     → WAITING_RETRY              (failed while waiting)
WAITING_SUBTASKS_OR_HOOKS     → ENDED_FAILURE_EXCEPTION    (failed, retries exhausted)
WAITING_SUBTASKS_OR_HOOKS     → ENDED_CANCELLED            (cancelling)
WAITING_SUBTASKS_OR_HOOKS     → ENDED_STOPPED              (stopping)

WAITING_RATELIMIT             → WAITING_QUEUE     (capacity returned)
WAITING_RATELIMIT             → ENDED_CANCELLED   (cancelled while waiting)
WAITING_RATELIMIT             → ENDED_STOPPED     (stopped while waiting)

WAITING_DEPENDENCY            → ENDED_CANCELLED   (dependency-based cancel)
WAITING_DEPENDENCY            → ENDED_STOPPED     (external stop)

NEW                           → ENDED_CANCELLED   (direct cancel)
NEW                           → ENDED_STOPPED     (direct stop)
WAITING_RETRY                 → ENDED_CANCELLED   (direct cancel)
WAITING_RETRY                 → ENDED_STOPPED     (direct stop)
```

**Key design decisions**:

1. **Atomic multi-from transitions**: States like `WAITING_DEPENDENCY` accept
   from both `NEW` and `WAITING_RETRY` using `status_detail__in=[...]` in the
   WHERE clause.

2. **Two-level status**: `status` (coarse) + `status_detail` (granular) allows
   efficient queries at both levels.

3. **No retry for rate limits**: `WAITING_RATELIMIT` doesn't consume retry
   budget — it's capacity queuing, not failure.

4. **Root-task guard**: `start_running()` checks that the session's root task
   hasn't been cancelled before activating child calls.

### 5.2 AgentTaskRun FSM

The task run FSM is defined in `runtime/tasks/run_fsm.py`. Simpler than the
call FSM — it tracks the lifecycle of a single execution attempt.

```
NEW   → QUEUED    (scheduler enqueues)
QUEUED → ACTIVE   (worker picks up)
ACTIVE → SUCCESS  (execution succeeded)
ACTIVE → FAILURE  (execution failed)
ACTIVE → RATE_LIMITED (LLM capacity exhausted)
ACTIVE → WAITING_RESULTTASKS (sub-calls pending)

SUCCESS → QUEUED (retry, only if explicitly triggered)
FAILURE → QUEUED (retry)
```

---

## 6. LLM Error Classification & Recovery

### 6.1 The Problem

LLM providers return different error formats for the same failure type:
- OpenAI returns 429 with `rate_limit_remaining`
- Anthropic returns 503 with `ThrottlingException`
- Vertex AI returns 429 wrapped as `BadRequestError`
- 404 means model ID doesn't exist
- 401/403 means authentication failure

All of these need **different recovery strategies**.

### 6.2 Error Classification (`llm_errors.py`)

The `classify_llm_error()` function parses exceptions into `LLMErrorInfo`
objects with these fields:

```python
@dataclass
class LLMErrorInfo:
    kind: str                    # rate_limit, model_not_found, auth, timeout,
                                 # bad_request, server, connection, unknown
    message: str
    status_code: int | None
    retry_after: float | None    # provider-specified cooldown
    scope: str                   # request | model | key | provider
    health_status: str           # HealthStatus value to set
    sticky: bool                 # True for non-recoverable errors
    config_like: bool            # True for user-request errors (don't poison health)
```

**Classification priority**:

1. **Rate limit** (429, 503, RateLimitError, ServiceUnavailableError, Timeout,
   Vertex 429 via string matching) → `RATE_LIMITED` health
2. **Model not found** (404, NotFoundError, "model_not_found") → `UNAVAILABLE`,
   sticky (won't recover by waiting)
3. **Auth error** (401, 403, AuthenticationError, PermissionDeniedError) →
   `AUTH_ERROR`, sticky
4. **Timeout** (408, Timeout) → `DEGRADED`
5. **Bad request** (400, 422, BadRequestError) → `CONFIG_ERROR` if the message
   looks like a config issue (contains "invalid model", "does not support", etc.),
   else empty (don't poison health for user-request errors)
6. **Server error** (5xx) → `DEGRADED`
7. **Connection error** (APIConnectionError) → `DEGRADED`
8. **Unknown** → no health change

### 6.3 Health Status Propagation

When an error is classified, the **AiModel** row is updated:

```python
# In call_llm_direct or the error handler:
error_info = classify_llm_error(exc)
if error_info.health_status:
    model.model_health = error_info.health_status
    model.model_error_count += 1
    model.backoff_until = timezone.now() + cooldown
    model.model_health_updated_at = timezone.now()
    model.save()
```

**Health behavior**:
- `HEALTHY` — normal operation
- `DEGRADED` — temporarily impaired, backoff window active
- `RATE_LIMITED` — provider is rate limiting, backoff window active
- `UNAVAILABLE` — model won't work until fixed (sticky)
- `AUTH_ERROR` — API key is revoked (sticky)
- `CONFIG_ERROR` — model config is wrong (sticky if config_like=True)

**`health_blocks_calls()`** prevents calls to models that are UNAVAILABLE or
AUTH_ERROR, and blocks DEGRADED/RATE_LIMITED models during their backoff
window.

### 6.4 Retry-After Extraction

`extract_retry_after_seconds()` looks for provider-specified cooldown in:

1. `litellm.RateLimitError.response.headers["Retry-After"]`
2. Wrapped `httpx.Response` headers
3. Text patterns: `"retry in 58s"`, `"retryDelay": "58s"`, `"retry-after: 30"`

This value is passed to `schedule_retry()` to set the appropriate `dont_start_before`.

---

## 7. Rate Limiting & Capacity Management

### 7.1 Multi-Level Rate Limiting

AgentOne uses a **multi-layered rate limiting** approach:

1. **Provider-level** (per `ApiProvider`): tracks total requests per minute
   across all models for a provider
2. **Model-level** (per `AiModel`): tracks per-model limits within a provider
3. **Key-level** (per `AiProviderRateLimit.key_name`): per-API-key limits
4. **Session-level**: per-session rate limiting (prevents one session from
   exhausting provider capacity)

### 7.2 Rate Limit States

```
Normal → RATE_LIMITED → WAITING_RATELIMIT (call) → WAITING_QUEUE → ACTIVE_QUEUED → ...
```

When `AgentTaskRun.apply()` returns `status=RATE_LIMITED`:

1. The run is marked `RATE_LIMITED` (terminal for this run)
2. The call transitions `ACTIVE_RUNNING → WAITING_RATELIMIT`
3. Retry budget is **not consumed** (it's capacity queuing)
4. The scheduler's `tick()` monitors `WAITING_RATELIMIT` calls
5. When `rate_limiter.check_capacity()` reports capacity, the call is released
   via `release_rate_limit()` → `WAITING_QUEUE`
6. A new run is dispatched via `start_new_taskrun()`

### 7.3 Rate Limiter Implementation

```python
class AgentRateLimiter:
    """Multi-provider rate limiter with sliding window."""
    
    def check_capacity(self, provider_name: str, model_name: str) -> bool:
        """Returns True if capacity is available."""
        # Check Redis-backed RateLimitBucket
        # Returns False if rate limited
        ...
    
    def record_request(self, provider_name, model_name, is_rate_limited, retry_after=None):
        """Record a request and update capacity state."""
        ...
    
    def get_retry_after(self, provider_name, model_name) -> float | None:
        """Get the recommended wait time."""
        ...
```

### 7.4 Model Switching on Rate Limits

When a call is rate-limited, the system attempts to switch to a **sibling model**
(same canonical name, different provider):

```python
# In call_runtime.py or call_scheduler.py:
if rate_limited and sibling_models:
    new_model = random.choice(sibling_models)
    # Update the call's model context
    # Re-dispatch with new model
```

This is transparent to the user — they see "model switch" in the task call log
but the conversation continues.

---

## 8. Model Switching

### 8.1 When Switching Occurs

Model switching happens in these scenarios:

1. **Rate limit on current model** — try sibling provider for same model name
2. **Model not found / config error** — skip to next available model
3. **Auth error** — try different provider with same model
4. **User manual selection** — user picks a model from dropdown
5. **Health recovery** — backoff expires, model becomes available again

### 8.2 Model Selection (`aimodel_picker.py`)

```python
# available_aimodels() — all enabled models with working API keys
# selectable_aimodels() — available models that aren't health-blocked
# model_groups() — grouped by canonical name (e.g. "gpt-4o" has OpenAI, Azure, etc.)
# sibling_aimodels(model) — other providers offering the same model name
```

### 8.3 Sibling Selection Logic

```python
def sibling_aimodels(model, *, exclude=None) -> List[AiModel]:
    """Return usable sibling models (same name, different provider)."""
    siblings = AiModel.objects.filter(
        name=model.name,
        enabled=True,
        api_provider_id__in=other_providers,
    ).exclude(pk=model.pk)
    # Filter out health-blocked
    return [s for s in siblings if not s.health_blocks_calls()]
```

### 8.4 Health-Aware Selection

When picking a model, the picker prefers:
1. **Usable** (enabled, has API key)
2. **Not health-blocked** (not UNAVAILABLE, not AUTH_ERROR, backoff expired)
3. **Random weighted toward least-loaded** (load balancing across providers)

---

## 9. Data Storage Layout

### 9.1 Database (Django ORM)

| Table | Purpose |
|---|---|
| `server_agentsession` | Session state, model selection |
| `server_agentmessage` | User and agent messages |
| `server_agent` | Agent configuration |
| `server_taskdefinition` | Task templates |
| `server_agenttaskcall` | Task call instances + FSM state |
| `server_agenttaskrun` | Task run instances + execution results |
| `server_aimodel` | Model metadata + health state |
| `server_apiprovider` | Provider configuration |
| `server_apiprovideraikv` | Encrypted API keys |
| `server_apiproviderratelimit` | Persistent rate limit state |
| `server_usermodelpreference` | User preferences |

### 9.2 Filesystem (`.agentone/`)

| Path | Contents |
|---|---|
| `.agentone/agents/` | Agent YAML manifests + `agent.md` configs |
| `.agentone/scripts/` | UI tool YAML manifests + scripts |
| `.agentone/skills/` | Skill YAML manifests |
| `.agentone/streams/` | Data flow definitions |
| `.agentone/sets/` | Set definitions |
| `.agentone/var/` | Session-private folders, logs, cache |

### 9.3 Session-Private Folders

Each scope owns its `var/sessions/` subtree:
- **Global**: `~/.agentone/var/sessions/<agent>/<pk>/`
- **Project**: `<project_dir>/var/sessions/<agent>/<pk>/`

Contents: tool outputs, scratch files, cached data. Owned folders are
guardrail-allowed; other sessions' folders are always denied.

### 9.4 Redis

| Key Pattern | Purpose |
|---|---|
| `agentone:ratelimit:*` | Rate limit buckets (provider/model) |
| `agentone:taskcall:*` | Pending task calls queue |
| `agentone:channel:*` | SSE channel subscriptions |
| `agentone:cache:*` | General cache |
| Celery queue | Task dispatch queue |

---

## 10. Integration Points

### 10.1 Celery

- **Workers**: Execute `AgentTaskRun.apply()` via Celery tasks
- **Beat**: Runs 5-second tick for CallScheduler + RunScheduler
- **Heartbeat**: 2-minute check to detect stuck workers

### 10.2 SSE (Server-Sent Events)

- `/sse/session/<pk>/` endpoint
- Uses Django Channels (ASGI) for persistent connections
- Events published via model-level `publish_by_pk()` (Django signals)
- Subscribers receive real-time status updates

### 10.3 litellm

- **`call_llm_direct` task**: Central LLM dispatch
- Uses `litellm.completion()` for all provider calls
- Handles provider routing, fallback, streaming
- Returns structured `AgentTaskRunResult`

### 10.4 Camoufox Browser

- Daemon mode: long-lived browser process
- Client: `runtime/browser/client.py` communicates with daemon
- Tab/session scope: each browser session has isolated state
- Controlled by launcher supervisor

### 10.5 External Tool Registry

- Tools defined as YAML scripts in `.agentone/scripts/`
- Registered via `scripts.md` manifest
- Must return `(bool, dict)` for UI tools
- Guardrail-validated before execution

---

## 11. Key Architectural Decisions

### 11.1 Two-Level State Machine (Call + Run)

**Decision**: Separate `AgentTaskCall` (what to do) from `AgentTaskRun` (did it).

**Rationale**: 
- A call can have multiple runs (retries, model switches)
- Each run has independent timing, result, and error
- The call FSM tracks the logical state; the run FSM tracks execution state
- Enables retry without losing original intent

### 11.2 Atomic FSM Transitions

**Decision**: All state transitions use atomic `UPDATE ... WHERE from_state` queries.

**Rationale**:
- Prevents race conditions in concurrent Celery workers
- Returns boolean success/failure for caller to handle races
- No locking required (DB handles concurrency)
- Simple to reason about correctness

### 11.3 Redis-Backed Rate Limiting

**Decision**: Rate limit state lives in Redis, not the database.

**Rationale**:
- Rate limit checks need to be fast (per-request)
- Redis supports atomic operations (INCR, SETEX, TTL)
- State is ephemeral (resets on server restart) — fine for rate limits
- Persistence layer (`AiProviderRateLimit`) exists for audit/debug

### 11.4 Health-Based Model Selection

**Decision**: Models have per-provider health state that blocks calls.

**Rationale**:
- Prevents repeated failed calls to known-broken models
- Different failure types need different handling (sticky vs temporary)
- Siblings can be tried (same model, different provider)
- Health is per-provider (not global model) — one provider's outage doesn't
  affect another's availability

### 11.5 Error Classification Over Generic Catch

**Decision**: All LLM errors are classified into structured `LLMErrorInfo`.

**Rationale**:
- Different errors need different recovery (retry vs skip vs auth fix)
- "Bad request" from user input must not poison model health
- Rate limits shouldn't consume retry budget
- Audit trail via `Response.error_type`

### 11.6 Tick-Based Scheduler

**Decision**: Scheduler runs on fixed 5-second intervals via Celery beat.

**Rationale**:
- Simple, predictable, no complex event loop needed
- Redis queue provides backpressure
- Tolerant to worker downtime (calls accumulate)
- Enough frequency for interactive use (< 5s perceived delay)

### 11.7 Scope-Based Path Resolution

**Decision**: All filesystem paths go through `runtime/paths.py` (`ScopeRef`).

**Rationale**:
- Global, user, project, workspace scopes have different path roots
- Never hardcode `~/.agentone/...` — always use `ScopeRef.resolve()`
- Prevents path leakage between scopes
- Enables testing with mock paths

### 11.8 Model Event Publishing

**Decision**: Each model publishes state changes via `publish_by_pk()`.

**Rationale**:
- SSE subscribers react to state changes without polling
- Task call updates flow from FSM transitions → event → SSE → UI
- Model health changes visible in real-time
- Django signals as the pub/sub backbone

---

## Appendix A: Request Flow — Complete Path

```
User types message → POST /sessions/<pk>/messages/
    │
    ├─> Django view creates AgentMessage
    │
    ├─> Calls session.ingest_user_message()
    │
    ├─> Session determines task type:
    │     - Slash command (starts with /)
    │     - Agent response (normal conversation)
    │
    ├─> CallScheduler._apply_async(task)
    │     │
    │     ├─> Create AgentTaskCall (NEW)
    │     ├─> enter_dependency_wait() → WAITING_DEPENDENCY
    │     ├─> Resolve argument dependencies
    │     ├─> request_approval() or enqueue_after_dependencies()
    │     └─> WAITING_QUEUE
    │
    ├─> CallScheduler tick (5s): picks up WAITING_QUEUE
    │     │
    │     ├─> pick_up() → ACTIVE_QUEUED
    │     ├─> RunScheduler._apply_async(taskrun_id)
    │     │     │
    │     │     ├─> TaskRunStateMachine.start() → ACTIVE
    │     │     ├─> TaskCallStateMachine.start_running() → ACTIVE_RUNNING
    │     │     ├─> taskrun.apply() ← executes the task
    │     │     │     │
    │     │     │     ├─> LLM call via call_llm_direct:
    │     │     │     │     - litellm.completion() to provider
    │     │     │     │     - On error: classify_llm_error()
    │     │     │     │     - Update AiModel health
    │     │     │     │     - Return error or result
    │     │     │     │
    │     │     │     ├─> RESULT → SUCCESS
    │     │     │     ├─> FAILURE → on_taskrun_ended()
    │     │     │     ├─> RATE_LIMITED → rate_limit() → WAITING_RATELIMIT
    │     │     │     └─> WAITING_RESULTTASKS → wait for refs
    │     │     │
    │     │     └─> CallScheduler.on_taskrun_ended(taskrun_id, status)
    │     │           │
    │     │           ├─> SUCCESS: succeed() → ENDED_SUCCESS
    │     │           ├─> FAILURE: schedule_retry() or fail()
    │     │           └─> MODEL SWITCH: try sibling_aimodels()
    │
    ├─> SSE events pushed to UI
    │
    └─> Session loop continues or ends
```

## Appendix B: Files by Responsibility

```
runtime/
├── session/
│   ├── session.py              # AgentSession: orchestration, agent loop
│   ├── aimodel_picker.py       # Model selection: groups, siblings, health
│   ├── agent_executor.py       # Agent execution: commands, tools, chains
│   └── session_folder.py       # Session-private folder management
├── tasks/
│   ├── call_scheduler.py       # CallScheduler: call creation, dispatch, hooks
│   ├── run_scheduler.py        # RunScheduler: run execution, result refs
│   ├── call_fsm.py             # TaskCallStateMachine: call state transitions
│   ├── run_fsm.py              # TaskRunStateMachine: run state transitions
│   └── run_runtime.py          # _apply_async: Celery worker entry point
├── rate_limiter.py             # AgentRateLimiter: capacity management
├── llm_errors.py               # classify_llm_error: error classification
├── browser/                    # Camoufox browser daemon + client
└── workitems/                  # WorkItem FSM + verifier
```