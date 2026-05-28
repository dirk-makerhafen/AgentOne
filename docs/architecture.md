# Architecture

## System overview

AgentOne is structured as a Django monolith with Celery for async task execution and a custom WebSocket UI framework (pyHtmlGui). Data flows from the browser through Django Channels into a reactive Python view layer, which drives the agent runtime and Celery task pipeline.

```
┌──────────────────────────────────────────────────────────────┐
│                          BROWSER                              │
│  pyhtmlgui JS client ────── WebSocket ──────► Django ASGI   │
│  (DOM sync, reconnect,        /ws                             │
│   ping, callbacks)                                            │
└──────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  UI LAYER (ui/)                             WebSocket thread  │
│                                                                 │
│  UiApp (Observable data model)                                  │
│    ├── Agents, Sessions, Skills, Pipes, Projects, Workspaces   │
│    │   (runtime wrapper collections)                            │
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
│  ├── Messages: Message → MessagePart → GenericContent          │
│  ├── Skills: SkillModel → SkillModelVersion                     │
│  ├── Pipes: NamedPipe → NamedPipeSubscription                   │
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
│  ├── Tasks    → BoundTask (session-bound task dispatch)         │
│  ├── Skills, Projects, Workspaces, Pipes, Crons                 │
│                                                                 │
│  State machines (atomic SQL updates):                            │
│  ├── call_fsm.py → TaskCallStateMachine:                        │
│  │   NEW→WAITING_DEPENDENCY→WAITING_QUEUE→                      │
│  │   ACTIVE_QUEUED→ACTIVE_RUNNING→ENDED_SUCCESS                 │
│  └── run_fsm.py → TaskRunStateMachine:                          │
│      NEW→QUEUED→ACTIVE→SUCCESS/FAILURE                          │
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
│    └── AdvanceTaskRuns → process QUEUED→ACTIVE transitions      │
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

- `AgentTaskCall` tracks call-level status (NEW→WAITING→ACTIVE→ENDED)
- `AgentTaskRun` tracks run-level status (NEW→QUEUED→ACTIVE→SUCCESS/FAILURE)
- Dependencies: calls reference other calls via M2M → `WAITING_DEPENDENCY`
- Auto-await: if a task returns an `AgentTaskCall`, parent run enters `WAITING_RESULTTASKS`

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

## Named pipes

Two-way agent communication:

- `NamedPipe` — named channel (unique name)
- `NamedPipeSubscription` — consumer config (task, agent, session mode, arguments template)
- Agents can write to pipes; subscribers consume and process
- Pipe output names on `TaskDefinitionVersion` link tasks to pipes they produce

## Configuration sources

| Source | What it configures |
|---|---|
| `config/settings.py` | Django settings, DB, Redis, Celery, installed apps |
| `config/settings_local.py` | Local overrides (gitignored) |
| `.agentone/agents/*/agent.md` | Agent definitions (model, tools, skills, settings) |
| `.agentone/scripts/*/scripts.md` | Tool group definitions (name→file mapping) |
| `.agentone/skills/skills.yaml` | Skill installation from repos |
| `server/models/settings.py` | `SettingsModel` — per-agent LLM settings |
| `server/models/providers/*.py` | `ApiProvider` + `AiModel` + `ApiKey` — LLM provider config |
