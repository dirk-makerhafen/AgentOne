# Core Runtime Mechanisms

Three interconnected subsystems power AgentOne's agent execution: the **task dispatch system** (how tools/tasks/commands are invoked), the **auto-await mechanism** (how results propagate across chains), and the **pyHtmlGui renderer** (how the UI stays in sync). This document covers each in depth.

---

## Task Dispatch System

The dispatch system is a layered pipeline: **BoundTask** → **TaskInstance** → **AgentTaskCall** → **AgentTaskRun**. Each layer adds a specific concern.

```
BoundTask.delay(args)
    │
    ▼
TaskInstance.apply_async(args, kwargs)    ← template instantiation, child instances
    │
    ▼
AgentTaskCall.apply_async()                ← lightweight "promise", tracks dependencies
    │
    ▼
CallScheduler._apply_async(call_pk)        ← arg dependency resolution, approval gating
    │
    ▼
AgentTaskRun.create() + apply_async()      ← resolves version, deserialises args
    │
    ▼
RunScheduler._apply_async(run_pk)          ← executes CHAIN/GROUP/FUNCTION
    │
    ▼
AgentTaskRun.apply()                       ← actual Python execution
```

### AgentTaskCall — The Promise

**File:** `server/models/tasks/agent_task_call.py`

An `AgentTaskCall` is a single logical invocation of a task definition. It is immutable after creation — state changes go through the `TaskCallStateMachine` which issues atomic SQL updates instead of calling `save()`.

**Key fields:**

| Field | Purpose |
|---|---|
| `task_definition` (FK→`TaskDefinition`) | Denormalized convenience ref for queries |
| `task_definition_version` (FK→`TDV`) | The specific version pinned at creation time |
| `session` / `session_version` | Owning session |
| `carguments_json` (JSON) | Serialized call arguments (including refs to other calls/runs/messages) |
| `parent_taskrun` (FK→`AgentTaskRun`) | The run that *created* this call (set via `ContextTracker.current`) |
| `taskcall_arg_references` (M2M→self) | Other calls whose results this call depends on as arguments |
| `taskcall_result_run` (FK→`AgentTaskRun`) | Set when the call completes — points to the final run that produced the result |
| `status` / `status_detail` | State machine position |

**Lifecycle states:**

```
NEW ──→ WAITING_DEPENDENCY ──→ [HALTED_APPROVAL] ──→ WAITING_QUEUE ──→ ACTIVE_QUEUED ──→ ACTIVE_RUNNING ──→ [WAITING_SUBTASK] ──→ ENDED_SUCCESS
                                       │                                                                    │
                                       └── WAITING_QUEUE ←── WAITING_RETRY ←──────────────────────────────────┘
                                                                                   └── WAITING_RATELIMIT ──→ WAITING_QUEUE
                                                                                   └── ENDED_FAILURE_EXCEPTION
```

**Key methods:**

- **`create()`** (line 156): Factory. Captures `ContextTracker.current` as `parent_taskrun`. Resolves before-run hooks serially (each hook's output feeds the next). Calls `create_call_arguments_json` to serialize arguments — any `AgentTaskCall`, `AgentTaskRun`, `Message`, `GenericContent`, `Query`, `Response` objects become `{"_type": ..., "pk": ...}` dicts; `AgentTaskCall` refs also populate `taskcall_arg_references` M2M.

- **`create_call_arguments_json()`** (line 258): Recursive serializer. For `AgentTaskCall` objects: stores `{"_type": "AgentTaskCall", "pk": pk}` and appends pk to `ref_pks`. For `AgentTaskRun`/`Message`/etc: stores `{"_type": ..., "pk": pk}` without appending to refs.

- **`get_result()`** (line 370): Blocks in a 1-second-poll loop until `self.status == ENDED`. Then delegates to `self.taskcall_result_run.get_result(...)`. Implements timeout and `allow_partial_results`.

- **`save()`** (line 406): **Immutable** — raises `ValidationError` if `self.pk` exists. Use state machine for transitions.

### AgentTaskRun — The Execution

**File:** `server/models/tasks/agent_task_run.py`

An `AgentTaskRun` is a single execution attempt. It resolves the exact `TaskDefinitionVersion` dynamically at create time (so retries see updated definitions), resolves arguments (including blocking on `AgentTaskCall` dependencies), executes the actual Python function or CHAIN/GROUP, and captures the result.

**Key fields:**

| Field | Purpose |
|---|---|
| `agent_task_call` (FK→`AgentTaskCall`) | The parent call |
| `task_definition_version` (FK→`TDV`) | **Dynamically resolved** at create time via `session.get_task/get_tool/get_command` |
| `arguments_json` (JSON) | Run-level arguments (merged instance defaults + call args/kwargs, then deserialised — `AgentTaskCall` refs resolved to their result `AgentTaskRun`s) |
| `taskrun_arg_references` (M2M→`AgentTaskRun`) | Runs whose results this run depends on |
| `taskrun_result_references` (M2M→`AgentTaskCall`) | Calls whose results this run **produced** — set by `_create_result_json` |
| `result_json` (JSON) | Serialised return value (or `{"exception": ..., "traceback": ...}` on failure) |
| `status` | `NEW` → `QUEUED` → `ACTIVE` → (`SUCCESS` | `FAILURE` | `RATE_LIMITED`) |

**State machine:**

```
NEW → QUEUED → ACTIVE → SUCCESS
                  ├──→ WAITING_RESULTTASKS → SUCCESS    (see auto-await below)
                  │                        └── FAILURE
                  └──→ FAILURE
```

**`apply()` — The core dispatch (line 182):**

Three branches based on `self.task_definition_version.task_execution_mode`:

1. **CHAIN mode** (line 197): Iterates `self.task_instance.child_instances.all()`, feeds each sub-task's `apply_async(kwargs=next_step_arguments)` the output of the previous. Result is the last call's return value. The `child_instances` are the ordered steps declared in the `chain:` list in `scripts.md`.

2. **GROUP mode** (line 206): Fires all `child_instances` in parallel with the same `arguments_json`. Result is a list of calls.

3. **FUNCTION mode** (line 212): Resolves `bound_task` via `session.get_task()`, calls `_resolve_run_arguments()` to deserialize args (blocks on dependencies with `timeout=0`), then calls `bound_task.call(*args, **kwargs)`.

After execution: passes result to `_create_result_json()`. If the result contains `AgentTaskCall` refs → `status=WAITING_RESULTTASKS`; otherwise `status=SUCCESS`. On `RateLimitError` → `status=RATE_LIMITED`. On any other Exception → `status=FAILURE` with exception JSON.

**`get_result()` (line 398):** Blocks in a 1-second-poll loop until `status in [SUCCESS, FAILURE]`. Then recursively deserialises `result_json` — any `{"_type": "AgentTaskCall", "pk": ...}` or `{"_type": "AgentTaskRun", "pk": ...}` with `recursive=True` triggers `.get_result()` on those objects, resolving the entire dependency tree. Rarely needs to be called because awaiting of results of normally done by the task dispatching logic

### BoundTask — The Session-Binding Layer

**File:** `runtime/tasks/bound_task.py`

A `BoundTask` ties a `TaskDefinitionVersion` to a specific session. It is created by `session.get_task(name)`, `session.get_tool(name)`, or `session.get_command(name)`.

**Key methods:**

- **`call(*args, **kwargs)`** (line 34): Synchronous execution. Imports the `.path` file via `importlib`, loads the `.function_name` function, and calls `func(self.session, *args, **kwargs)` if `bound=True` or `func(*args, **kwargs)` if `bound=False`. Raises `TypeError` for CHAIN/GROUP tasks (they have no Python file to call).

- **`apply_async(args, kwargs)`** (line 101): Calls `self.instance()` to get/create a `TaskInstance`, then `task_instance.apply_async(args=args, kwargs=kwargs)` → `TaskInstance.create_call()` → `AgentTaskCall.create()` → `call.apply_async()` → `celery_delay(CallScheduler._apply_async, call.pk)`.

- **`instance()`** (line 140): `TaskInstance.get_or_create()` — looks up or creates a `TaskInstance` matching `task_definition_version` + `session_version`. **This is where CHAIN/GROUP child instances are auto-created**: if the TDV has `child_tasks`, the method resolves those names into child `TaskInstance` records and stores them on `child_instances` M2M.

- **`delay(*args, **kwargs)`** (line 97): Shorthand for `apply_async(args, kwargs)`.

### ContextTracker — Parent-Child Tracking

**File:** `runtime/context_manager.py` (28 lines)

A `contextvars.ContextVar` that holds the current `AgentTaskRun` during execution. `AgentTaskRun.apply()` wraps execution in `with ContextTracker(self):`. Any `AgentTaskCall`s created during that run's execution have `parent_taskrun` pointing back to this run, establishing the full parent-child tree.

### The `ingest_user_message` Chain — End-to-End

This is the core agent loop. It demonstrates all the mechanisms working together:

```
Session.add_user_message(parts)
  │
  ▼
BoundTask("ingest_user_message").delay(parts=parts)
  │
  ▼
AgentTaskCall("ingest_user_message") ──→ AgentTaskRun
  │                                           │
  │                                     ingest_user_message(session, parts)
  │                                           │ create Message, return ...
  │                                           ▼
  │                                     BoundTask("process_turn").delay(message=message)
  │                                           │ returns an AgentTaskCall!
  │                                           ▼
  │◄── AgentTaskRun.apply() sees AgentTaskCall in result ──→ WAITING_RESULTTASKS
  │
  AgentTaskRun("process_turn")  ← CHAIN of 5 subtasks:
        │                          1. build_llm_context
        │                          2. call_llm
        ▼                          3. parse_llm_response
  AgentTaskRun("decide_next_step") 4. ingest_assistant_message
        │                          5. decide_next_step
        │
        ├── if tool calls made: return BoundTask("process_turn").delay(message=message)
        │      └──→ again WAITING_RESULTTASKS → loop continues
        │
        └── if turn ends: return Message object
               └──→ SUCCESS, result propagates up through every WAITING_RESULTTASKS
```

When `decide_next_step` returns an `AgentTaskCall` for `process_turn`, the framework chains back into the loop. When it returns a bare `Message`, the loop terminates and the `Message` propagates up through every `get_result(recursive=True)` call.

---

## Auto-Await / Result Resolution

The auto-await mechanism is what makes the framework feel synchronous despite the asynchronous task execution. The key insight: **returning an `AgentTaskCall` from a task function is semantically identical to awaiting it** — the framework blocks the parent run until the child call resolves, then transparently substitutes the result.

### Stage 1 — Result Serialisation

**File:** `agent_task_run.py:376` (`_create_result_json`)

After `AgentTaskRun.apply()` executes the task function, the return value is passed to `_create_result_json()`:

```python
def _create_result_json(self, result):
    ref_pks = []
    result_json = self._create_result_json_recursive(result, ref_pks)
    if ref_pks:
        self.taskrun_result_references.set(ref_pks)
    return result_json, ref_pks
```

The recursive serializer scans the result for `AgentTaskCall` instances. Each one is converted to `{"_type": "AgentTaskCall", "pk": pk}` and its pk is appended to `ref_pks`. `AgentTaskRun`, `Message`, `Query`, `Response` instances are also serialised as `{"_type": ..., "pk": ...}` but **not** added to `ref_pks` (only `AgentTaskCall` refs trigger waiting).

### Stage 2 — WAITING_RESULTTASKS Transition

Back in `apply()`, if `ref_pks` is non-empty → `self.status = WAITING_RESULTTASKS`. If empty → `SUCCESS`.

This means: **any task that returns an `AgentTaskCall` (directly, nested in a dict, or nested in a list) causes the framework to wait for that call to complete before marking the run as successful.**

### Stage 3 — RunScheduler Polling

**File:** `run_scheduler.py:54`

`RunScheduler._apply_async()` calls `run.apply()`, then checks `run.status`. If `WAITING_RESULTTASKS` and not all referenced calls have ended → parks the parent call in `WAITING_SUBTASK`. When the child calls reach `ENDED`, the `RunScheduler` is notified via `taskrun_result_reference_ended()` (line 76), which decrements the wait counter. Once zero → `all_taskrun_result_references_ended()` (line 100) → `TaskRunStateMachine.succeed()`.

### Stage 4 — Recursive `get_result()`

Both `AgentTaskCall.get_result()` and `AgentTaskRun.get_result()` have a `recursive=True` option:

- **`AgentTaskCall.get_result()`** (line 370): Waits for `status == ENDED`, then delegates to `self.taskcall_result_run.get_result(recursive=True)`.
- **`AgentTaskRun.get_result()`** (line 398): Waits for `status in [SUCCESS, FAILURE]`, then deserialises `result_json` recursively — any `{"_type": "AgentTaskCall", "pk": ...}` or `{"_type": "AgentTaskRun", "pk": ...}` with `recursive=True` triggers `.get_result()` on those objects.

This means calling `get_result(recursive=True)` on the root call blocks until the entire tree of nested task calls has resolved, and returns the final value (e.g., a `Message` at the leaf).

### Key Implication for Tool Authors

When you return an `AgentTaskCall` from a tool/task function (e.g., `session.get_task("process_turn").delay(message=msg)`), the framework **automatically substitutes** that call with its eventual result. The parent call never sees the `AgentTaskCall` object — it sees the resolved value (e.g., a `Message`). This is the mechanism behind the `delegate_task` tool:

```python
def delegate_task(session, subagent_name, query):
    # ...
    taskcall = child_session.add_user_message(parts=parts)
    return {"result": taskcall, "session_pk": child_session.model.pk}
```

The `taskcall` is an `AgentTaskCall`. When the parent receives this dict, the framework serialises it, finds the `AgentTaskCall` ref, enters `WAITING_RESULTTASKS`, waits for the subagent's entire chain to resolve, then transparently substitutes the `AgentTaskCall` with the final `Message`. The parent never blocks in its own code — it just returns the call and the framework handles the rest.

---

## pyHtmlGui Renderer

pyHtmlGui is a custom WebSocket-based UI framework built on Jinja2 templates and Django Channels. It maintains an in-memory view tree on the server, renders it to HTML, and sends surgical DOM updates (not full pages) over the WebSocket.

### Architecture Overview

```
Browser                          Django Channels                    Python Runtime
───────                          ───────────────                    ──────────────
pyHtmlGuiBase.html               ASGI: ws → PyHtmlGuiConsumer       UiApp (Observable)
  └─ pyhtmlgui.js                      └─ PyHtmlGuiInstance              └─ projects, agents,
       │                                    └─ UiAppView                       sessions, messages
       │                                          ├─ AppTitlebar
       │                                          ├─ RailView
       │                                          ├─ SidebarView
       │                                          ├─ MainView
       │                                          │     └─ open_tabs dict
       │                                          │           ├─ AgentView
       │                                          │           └─ Chat
       │                                          └─ RightPanel
       │                                                ├─ Workspace
       │                                                ├─ Session
       │                                                ├─ Tasks
       │                                                └─ Subagents
       │
pyview.method() ────── WebSocket JSON ──────►  _on_subject_updated()
       ▲                                           │
       │                                      self.update()
       │                                           │
       │                                     render() → HTML
       │                                           │
       pyhtmlgui. ◄────── WebSocket JSON ──────────┘
       replace_element(uid, html)
```

### View Hierarchy

**Base class:** `PyHtmlView` (`ui/lib/pyHtmlGui/pyhtmlgui/view/pyhtml_view.py`)

Every UI component extends `PyHtmlView`. Key class attributes:

| Attribute | Default | Purpose |
|---|---|---|
| `TEMPLATE_STR` | `None` | Inline Jinja2 template string |
| `TEMPLATE_FILE` | `None` | Path to Jinja2 template file |
| `DOM_ELEMENT` | `"div"` | HTML element tag name |
| `DOM_ELEMENT_CLASS` | `None` | CSS class for the element |
| `CSS_STR` | `None` | Inline CSS added to the page |

**Constructor** (line 26): Generates a random 16-char `uid`. Registers as child of parent. Creates weak references to subject and parent. Resolves `_instance` to the `PyHtmlGuiInstance`. Auto-observes subject if `_on_subject_updated` is defined (calls `add_observable(self.subject)`).

**Convenience base:** `ModelView` (`ui/lib/model_view.py`): Stores subject and parent as direct attributes (not weak refs). Provides `_on_subject_updated() → self.update()` and `_on_subject_died()`.

### Render Pipeline

1. **Trigger:** Something calls `view.update()` — typically from `_on_subject_updated()` (called when an observable subject changes) or from a JS click handler.

2. **`render()`** (line 64):
   - Gets a hard reference to subject (preventing GC during render).
   - Calls `self.set_visible(True)` if not visible.
   - Marks all children `_was_rendered = False`.
   - Gets the cached Jinja2 template via `self._instance.get_template(self)`.
   - Renders template with `{"pyview": self}` — **this is the only variable injected**.
   - Hides children that were NOT rendered (disappeared from template).
   - Wraps output in DOM element tags: `<div class="ClassName" id="pv_xxx">...</div>`.

3. **`update()`** calls `pyhtmlgui.replace_element` via WebSocket, passing the new HTML for this view's `uid`. JS replaces the existing element in-place.

4. **Template resolution** (`pyhtmlgui_instance.py:187`):
   - If `view.TEMPLATE_FILE` is set → loads from file via `jinja2.FileSystemLoader`.
   - Otherwise uses `view.TEMPLATE_STR`.
   - A regex preprocessor (`_prepare_template`, line 253) rewrites `onclick="pyview.method(args)"` → `onclick="pyhtmlgui.call(functioncall_id, args)"`. This is what enables Python methods to be called from browser click handlers.

5. **Update modes:**
   - `update()` — full re-render of the view and its children, replaces the DOM element.
   - `insert_element(index, html)` — surgical insertion at a specific position (used by `ObservableListView` for single-item insertions).
   - `delete()` — removes from DOM and detaches from parent.

### Observable Data Structures

**File:** `ui/lib/pyHtmlGui/pyhtmlgui/lib/`

- **`Observable`** (`observable.py:5`): Base mixin with `_observers` (WeakFunctionReferences). `attach_observer()`, `detach_observer()`, `notify_observers(**kwargs)`.

- **`ObservableList(list, Observable)`** (`observableList.py:4`): Inherits from both `list` and `Observable`. Overrides every mutating method to call `notify_observers()` with a payload describing the action:
  - `append` → `{"action": "append", "index": N, "item": ...}`
  - `insert` → `{"action": "insert", "index": N, "item": ...}`
  - `__setitem__` → `{"action": "setitem", "index": N, "old_item": ..., "new_item": ...}`
  - `__delitem__` → `{"action": "delitem", "index": N, "item": ...}`
  - And so on for `extend`, `pop`, `remove`, `sort`, `reverse`, `clear`.

- **`ObservableDict(dict, Observable)`** (`observableDict.py:4`): Same pattern for dict mutations.

### Observable Views

**`ObservableListView`** (`view/observable_list_view.py:11`): Renders items from an `ObservableList`. Constructor takes `item_class` (a `PyHtmlView` subclass for wrapping each item). The `_on_subject_updated()` method handles each mutation type:

- `append`/`insert`: Creates a wrapper view, calls `insert_element(index, obj)` for surgical DOM insertion.
- `setitem`: Deletes old wrapper, creates new one, inserts at index.
- `extend`: Inserts multiple items sequentially.
- `remove`/`pop`/`delitem`: Deletes wrapper from DOM and list.
- `sort`/`reverse`/`clear`: Full re-render.

**`ObservableDictView`** (`view/observable_dict_view.py:15`): Same concept for `ObservableDict`. Each wrapper gets an `element_key` method returning its dict key (used for sorted iteration).

**`QuerySetView`** (`ui/lib/queryset_view.py:10`): Lazily renders Django QuerySet results. `_recreate()` destroys old wrappers and builds new ones from the queryset. Uses `first_or_create_view` helper to avoid building views for items outside the visible range.

### Right Panel Architecture

**File:** `ui/main/rightpanel/rightpanel.py`

The `RightPanel` (line 19) manages four tab sub-views via a `switchPanel(name)` method:

| Tab | View class | Purpose |
|---|---|---|
| Workspace | `RightPanelWorkspace` | Filesystem tree for the current session's workspace |
| Session | `RightPanelSession` | Session detail with settings overrides + reset buttons |
| Tasks | `RightPanelTasks` | Capability tables (allowed/disallowed tools/tasks/commands/skills/subagents) |
| Sub-agents | `RightPanelSubagents` | Available subagents + active child sessions |

The `current_session` property (line 61) resolves to the active chat session by inspecting `self.parent.main_panel.selected_tab_view.session`:

```python
@property
def current_session(self):
    mtv = getattr(self.parent, 'main_panel', None)
    mtv = getattr(mtv, 'selected_tab_view', None) if mtv else None
    if mtv and hasattr(mtv, 'session') and isinstance(mtv.session, Session):
        return mtv.session
    return None
```

Each tab view accesses `self.parent.current_session` to get the active runtime `Session`. This is the standard pattern — views never directly query the database for session state; they go through the parent's `current_session` property.

### Template Patterns

Templates receive only `{"pyview": self}` as context. Common patterns:

**Rendering child views:**
```jinja
{{ pyview.sidebar.render() }}
{{ pyview.main_panel.render() }}
```

**Iterating items:**
```jinja
{% for item in pyview.get_items() %}
  {{ item.render() }}
{% endfor %}
```

**Conditional rendering:**
```jinja
{% if pyview.subject.is_active %}
  <span class="status active">Active</span>
{% else %}
  <span class="status inactive">Inactive</span>
{% endif %}
```

**JS callbacks via pyview:**
```html
<button onclick="pyview.toggle('{{ name }}')">Toggle</button>
```

The `_prepare_template()` preprocessor rewrites these to `pyhtmlgui.call(N, 'name')` at compile time, where `N` is an auto-generated function reference ID.

### CSS Scoping

The framework supports inline CSS per view class via `CSS_STR`. When a view is first rendered, its `CSS_STR` is injected into the page. CSS rules are scoped by the view's class name, so they don't leak:

```python
class DirectoryView(ModelView):
    CSS_STR = """
    .DirectoryView { font-family: monospace; }
    .DirectoryView .folder { font-weight: bold; }
    """
```

### Event Flow Summary

```
User clicks button in browser
  │
  ▼
preprocessed onclick="pyhtmlgui.call(42, 'toggle', 'src')"
  │
  ▼
WebSocket message: {"call_id": 42, "args": ["toggle", "src"]}
  │
  ▼
PyHtmlGuiConsumer.receive() → pyhtmlgui_instance.process_received_message()
  │
  ▼
Resolves call_id 42 → PyHtmlView.fn_refs[42] → BoundMethod(instance.toggle)
  │
  ▼
toggle('src') runs Python code (e.g., toggles a directory in workspace tree)
  │
  ▼
toggle() calls self.update()
  │
  ▼
update() → render() → HTML → ws.send({"name": "pyhtmlgui.replace_element",
                                        "args": ["pv_abc123", "<div>...</div>"]})
  │
  ▼
Browser JS: document.getElementById("pv_abc123").outerHTML = newHTML
```

No page reloads. No full re-renders. Only the specific view that called `update()` gets its DOM replaced.

---

## File Reference

### Task Dispatch

| File | Lines | Content |
|---|---|---|
| `server/models/tasks/agent_task_call.py` | 36–153 | Fields |
| | 156–245 | `AgentTaskCall.create()` |
| | 258–306 | `create_call_arguments_json()` |
| | 308–368 | `_resolve_call_arguments()` |
| | 370–404 | `get_result()` |
| `server/models/tasks/agent_task_run.py` | 39–100 | Fields |
| | 102–171 | `AgentTaskRun.create()` |
| | 182–248 | `apply()` (CHAIN/GROUP/FUNCTION dispatch) |
| | 250–302 | `_create_run_arguments_json()` |
| | 304–374 | `_resolve_run_arguments()` |
| | 376–396 | `_create_result_json()` |
| | 398–481 | `get_result()` |
| `runtime/tasks/bound_task.py` | 34–76 | `call()` |
| | 97–99 | `delay()` |
| | 101–138 | `apply_async()` |
| | 140–157 | `instance()` |
| `runtime/tasks/call_scheduler.py` | 22–39 | `_apply_async()` entry |
| | 121–143 | `start_new_taskrun()` |
| | 146–199 | `on_taskrun_ended()` |
| | 256–356 | `_on_taskcall_ended()` |
| `runtime/tasks/run_scheduler.py` | 23–69 | `_apply_async()` with WAITING_RESULTTASKS |
| | 76–98 | `taskrun_result_reference_ended()` |
| | 100–116 | `all_taskrun_result_references_ended()` |
| `runtime/context_manager.py` | 6–28 | `ContextTracker` |
| `runtime/session/session.py` | 236–242 | `get_task()` / `get_tool()` / `get_command()` |
| | 448–480 | `add_user_message()` |
| `.agentone/agents/baseagent/scripts/ingest_user_message.py` | 14–50 | `ingest_user_message()` |
| `.agentone/agents/baseagent/scripts/decide_next_step.py` | 19–62 | `decide_next_step()` |
| `.agentone/agents/baseagent/scripts/scripts.md` | 35–42 | `process_turn` CHAIN definition |

### pyHtmlGui Renderer

| File | Lines | Content |
|---|---|---|
| `ui/lib/pyHtmlGui/pyhtmlgui/pyhtmlgui.py` | 18–180 | Top-level framework |
| `ui/lib/pyHtmlGui/pyhtmlgui/pyhtmlgui_instance.py` | 38–281 | Instance, template cache, `_prepare_template()` |
| `ui/lib/pyHtmlGui/pyhtmlgui/view/pyhtml_view.py` | 18–242 | Base `PyHtmlView` class |
| `ui/lib/pyHtmlGui/pyhtmlgui/view/observable_list_view.py` | 11–147 | ObservableListView |
| `ui/lib/pyHtmlGui/pyhtmlgui/view/observable_dict_view.py` | 15–99 | ObservableDictView |
| `ui/lib/pyHtmlGui/pyhtmlgui/lib/observable.py` | 5–20 | Observable base |
| `ui/lib/pyHtmlGui/pyhtmlgui/lib/observableList.py` | 4–72 | ObservableList |
| `ui/lib/pyHtmlGui/pyhtmlgui/lib/observableDict.py` | 4–38 | ObservableDict |
| `ui/consumer.py` | 16–44 | WebSocket consumer |
| `ui/app_view.py` | 37–78 | Root UiAppView |
| `ui/lib/model_view.py` | 13–31 | ModelView convenience base |
| `ui/lib/queryset_view.py` | 10–107 | QuerySetView |
| `ui/main/rightpanel/rightpanel.py` | 19–78 | RightPanel with tab switching |
| `ui/main/rightpanel/workspace.py` | 51–189 | Workspace tab with DirectoryView |
| `ui/main/rightpanel/session.py` | 11–161 | Session detail tab |
| `ui/main/rightpanel/tasks.py` | 36–125 | Capability tables tab |
| `ui/main/rightpanel/subagents.py` | 28–154 | Subagents tab |
| `ui/main/agent/agent_view.py` | 55–437 | Agent detail view |
