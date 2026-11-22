# Core Runtime Mechanisms

Three interconnected subsystems power AgentOne's agent execution: the **task dispatch system** (how tools/tasks/commands are invoked), the **auto-await mechanism** (how results propagate across chains), and the **pyHtmlGui renderer** (legacy UI only; the primary UI is `webui/` with htmx + SSE — see [`ui-rewrite.md`](ui-rewrite.md)). This document covers each in depth.

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
NEW ──→ WAITING_DEPENDENCY ──→ [HALTED_APPROVAL] ──→ WAITING_QUEUE ──→ ACTIVE_QUEUED ──→ ACTIVE_RUNNING ──→ [WAITING_SUBTASKS_OR_HOOKS] ──→ ENDED_SUCCESS
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

Branches based on `self.task_definition_version.task_execution_mode`:

1. **CHAIN mode** (line 197): Iterates `self.task_instance.child_instances.all()`, feeds each sub-task's `apply_async(kwargs=next_step_arguments)` the output of the previous. Result is the last call's return value. The `child_instances` are the ordered steps declared in the `chain:` list in `scripts.md`.

2. **GROUP mode** (line 206): Fires all `child_instances` in parallel with the same `arguments_json`. Result is a list of calls.

3. **FUNCTION mode** (line 220): Resolves `bound_task` via `session.get_task()`, calls `_resolve_run_arguments()` to deserialize args (blocks on dependencies with `timeout=0`), then calls `bound_task.call(*args, **kwargs)`.  **SCRIPT mode** also falls into this branch — the ``else`` block dispatches both FUNCTION and SCRIPT to ``bound_task.call()``, where ``call()`` detects the mode and runs the executable directly instead of importing a Python module.

After execution: passes result to `_create_result_json()`. If the result contains `AgentTaskCall` refs → `status=WAITING_RESULTTASKS`; otherwise `status=SUCCESS`. On `RateLimitError` → `status=RATE_LIMITED`. On any other Exception → `status=FAILURE` with exception JSON.

**`get_result()` (line 398):** Blocks in a 1-second-poll loop until `status in [SUCCESS, FAILURE]`. Then recursively deserialises `result_json` — any `{"_type": "AgentTaskCall", "pk": ...}` or `{"_type": "AgentTaskRun", "pk": ...}` with `recursive=True` triggers `.get_result()` on those objects, resolving the entire dependency tree. Rarely needs to be called because awaiting of results of normally done by the task dispatching logic

### BoundTask — The Session-Binding Layer

**File:** `runtime/tasks/bound_task.py`

A `BoundTask` ties a `TaskDefinitionVersion` to a specific session. It is created by `session.get_task(name)`, `session.get_tool(name)`, or `session.get_command(name)`.

**Key methods:**

- **`call(*args, **kwargs)`** (line 34): Synchronous execution. For SCRIPT mode, executes the file as a subprocess (args → CLI, kwargs → JSON on stdin). For FUNCTION mode, imports the `.path` file via `importlib`, loads the `.function_name` function, and calls `func(self.session, *args, **kwargs)` if `bound=True` or `func(*args, **kwargs)` if `bound=False`. Raises `TypeError` for CHAIN/GROUP tasks (and legacy `MAP` rows — that mode is no longer dispatachable) because they have no callable file.

- **`apply_async(args, kwargs)`** (line 101): Calls `self.instance()` to get/create a `TaskInstance`, then `task_instance.apply_async(args=args, kwargs=kwargs)` → `TaskInstance.create_call()` → `AgentTaskCall.create()` → `call.apply_async()` → `celery_delay(CallScheduler._apply_async, call.pk)`.

- **`instance()`** (line 140): `TaskInstance.get_or_create()` — looks up or creates a `TaskInstance` matching `task_definition_version` + `session_version`. **This is where CHAIN/GROUP child instances are auto-created**: if the TDV has `child_tasks`, the method resolves those names into child `TaskInstance` records and stores them on `child_instances` M2M.

- **`delay(*args, **kwargs)`** (line 97): Shorthand for `apply_async(args, kwargs)`.

### `map` — Batch Fan-Out

**File:** `.agentone/scripts/core/map.py` (registered as the `map` task in
`.agentone/scripts/core/scripts.md`)

`map(_session, target, list_of_kwargs, concurrency=1, kind=None)` calls
`target` once per item:

- **Resolution:** `target` is looked up as a task, then a tool, then a
  command, through `session.get_task/get_tool/get_command` (so the usual
  allowlists apply). Pass `kind` to force one of them.
- **Items:** a dict is passed as kwargs (`{"path": "a.md"}` →
  `target(path="a.md")`); anything else is passed as the single positional
  argument.
- **One shared `TaskInstance`:** all item calls belong to the same instance,
  so a single `limit_per_instance_parallel_runs` value governs the batch.
  `map` overrides it per call with `concurrency` (`1` = one at a time in list
  order, `0` = unlimited, `N` = at most N admitted concurrently).
- **Depth-first per item:** an item's call only ends after every call it
  returned has ended, so with `concurrency=1` item N+1 starts only after item
  N's whole subtree (e.g. `update_timeline_item` → `llm_query` →
  `process_summary` → `double_check_summary`).
- **Return value:** the list of created `AgentTaskCall`s. Return it from the
  dispatching task and the framework auto-awaits the whole batch
  (`WAITING_RESULTTASKS`).

The `map` task's own TDV sets `limit_per_instance_parallel_runs: 0`, so a map
call does not queue unrelated batches behind itself (a map call only ends when
its batch ends).

Caveat: batches of the **same** target task in the same session share a
`TaskInstance`, so their admissions interleave. Keep one batch at a time per
target when ordering matters.

### Filesystem Access Policy — Guardrails

**File:** `runtime/workspace_access.py`

An optional `access:` block on a workspace (`WorkspaceModel.access`, DB-canonical)
and/or agent (`agent.md`) restricts which paths filesystem, shell, and Python
tools may read or write. See [docs/manifest-format.md](manifest-format.md) for the config
schema.

**Policy resolution** — `resolve_policy(session)` (line 175) merges the
workspace's `access:` block (the *base* in-workspace rules) with the agent's
`access:` block (`workspace:` override + `external:` rules). Sessions without a
workspace get an all-allow policy except for other sessions' private folders
(which stay denied). Each `read:`/`write:` action
resolves to an `ActionPolicy` (`default` posture + `allow`/`ask`/`deny` pattern
lists). Deny patterns from any scope are merged into a `global_deny` list that
wins everywhere.

**Evaluation** — `evaluate(policy, target, action)` (line 296) classifies a
path into `allow` / `ask` / `deny`:

- Global deny patterns are checked first (any scope, anywhere).
- Session-private storage carve-out second: paths under
  `~/.agentone/var/sessions/<agent>/<own_pk>/` are always `allow` (read and write),
  paths under another session's folder (or the base dir itself) are always
  `deny`. Only an explicit global `deny` pattern overrides the own-folder
  allow. Applies even to sessions without a workspace.
- `inside` vs `outside` is decided by `Path.relative_to(workspace_root)`;
  inside uses the workspace/override rules, outside the agent `external:` rules.
- Precedence per action: `deny` > `ask` > `allow` > `default`.
- `write` implies `read`: a read also honours the write policy's allow/ask lists.
- Targets are matched as globs (`fnmatch`) against the resolved absolute path,
  the raw absolute path (macOS `/tmp` → `/private/tmp` symlink form), and the
  workspace-relative form, so relative and absolute patterns both work.

**Enforcement happens in three layers:**

1. **Scheduling** — `CallScheduler._guardrail_filesystem_check` (in
   `runtime/tasks/call_scheduler.py`) runs before a filesystem tool is
   dispatched. The tool's posture is resolved via
   `task_access_posture(task_definition)` (prefers the manifest `access:` field,
   falls back to the `filesystem-read` / `filesystem-write` group convention);
   its absolute-path arguments are extracted by `extract_path_args`. An `ask`
   verdict sets `requires_approval=True` + `guardrail_reason` → the call enters
   `HALTED_APPROVAL`. `deny` verdicts are not routed to approval — they are
   enforced at execution.
2. **Guardrail content checks** — `check_shell_paths` / `check_python_paths`
   (in `runtime/guardrails.py`) analyse shell/python source for absolute
   filesystem targets. Shell classification is **whitelist-based and
   fail-safe**: commands in `_SHELL_READ_COMMANDS` (cat, grep, sort, diff,
   …) classify their absolute operands as reads; anything else (explicit
   writers like `cp`/`mv`/`rm`/`tar`, or any unknown command) is treated as
   write-capable. In-place write flags flip whitelisted commands to write
   (`sed -i`, `sort -o`, `perl -i`), redirect targets (`>`, `>>`, `2>`) are
   always writes, and device nodes (`/dev/...`) are ignored. Python analysis
   covers `open(..., "w")`, `os.remove`, `shutil.*`, `Path.write_*`, …). Their
   verdict is merged with the content-risk verdict
   (`_merge_guardrail_verdicts` — deny wins) before deciding approval.
3. **Execution** — `BoundTask._filesystem_access_block` (in
   `runtime/tasks/bound_task.py`) re-evaluates the call args at execution time.
   Any `deny` verdict hard-blocks the call and returns
   `(False, {status: error, stderr: reason, return_code: -1})` before the tool
   runs — no approval can override a deny.

Because `deny` is enforced at the execution boundary, a deny is a hard
guarantee even if a call bypasses the scheduler path (e.g. direct `BoundTask.call`).

### Session-Private Storage

**Files:** `runtime/session_folder.py`, `runtime/session/session.py`
(`private_dir` / `ensure_private_dir`), `runtime/session_bootstrap.py`

Every session owns an isolated private folder at
`<scope>/var/sessions/<agent>/<session_pk>/` — global/user sessions use
`<AGENTONE_SESSIONS_DIR>` (`~/.agentone/var/sessions` by default, overridable
via `config/settings_local.py`), project/workspace sessions use their own
scope's `var/`. It holds scratch files,
temporary memory, ad-hoc prompts/tools, intermediate results, generated
scripts and other session-specific artifacts; subsessions get their own
folder. Agents can announce it with `{{session_dir}}` in their
`sessionBootstrap` template (the built-in chat agents do). Bootstrap
messages are frozen history at the start of each compaction segment and are
re-embedded in the compaction marker after compaction. Agents use the normal
`filesystem-read`/`filesystem-write` tools — no special tools. Freezing the
announcement in history (instead of re-injecting it every turn) keeps the
prompt-cache prefix stable. Creation is lazy (`ensure_session_dir`, also
triggered by `BoundTask._ensure_private_dir_on_access` on first use; never
inside `evaluate()`, which stays a pure policy check). Folders holding scratch
files are kept forever (including archived sessions). The sweep removes
folders whose session row was hard-deleted, plus empty folders of ended
(`is_active=False`) sessions; it runs at startup
(`server/tasks/startup_cleanup.py`) and roughly every 10 minutes from the tick
scheduler (`_sweep_session_folders`).

Reusable query templates live in the database, not the folder
(`runtime/query_templates.py`, models `QueryTemplateVersion` +
`SessionQueryTemplate` in `server/models/queries/query_template.py`).
Each version is an immutable row pointing at content-addressed
`GenericContent` (frontmatter head with `name`, `description`, typed
`variables` + Jinja body, rendered with `StrictUndefined`); a session's
current template is a link row `(session, name, version)`. Saves mint a new
version and move only the writer's link, same-agent forks copy the parent's
links (`inherit_templates`, hooked into
`AgentVersionModel.get_or_create_session` and enabled only when
`inherit_links=True` — i.e. via `Session.fork`, never for a different-agent
`Session.spawn_subagent`), and deletes remove the link
only — version rows stay as the audit trail. The `template_*` tools
(`.agentone/scripts/core/query_template.py`) list/get/save/delete/render
them, and `template_execute` dispatches the rendered prompt through the
`call_llm_direct` ephemeral pipeline; the Templates panel
(`webui/chat/_panel_body.html`) offers the same flow in the UI and tracks the
run via the `AgentTaskCall.session:<sid>` observable.

### ContextTracker — Parent-Child Tracking

**File:** `runtime/context_manager.py` (28 lines)

A `contextvars.ContextVar` that holds the current `AgentTaskRun` during execution. `AgentTaskRun.apply()` wraps execution in `with ContextTracker(self):`. Any `AgentTaskCall`s created during that run's execution have `parent_taskrun` pointing back to this run, establishing the full parent-child tree.

### The `ingest_user_message` Chain — End-to-End

This is the core agent loop. It demonstrates all the mechanisms working together:

```
Session.add_user_message(message, execute_turn=True)
  │
  ▼
BoundTask("ingest_user_message").delay(message=..., execute_turn=...)
  │
  ▼
AgentTaskCall("ingest_user_message") ──→ AgentTaskRun
  │                                           │
  │                                     ingest_user_message(session, message, execute_turn)
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

A second, side-effect-free use of the same fork + auto-await pattern is
[automatic chat titling](auto-title.md): the first user message forks a
same-model copy of the session, a `final_result` title is captured, and a
parent-side task renames the chat unless the user has already named it.

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

`RunScheduler._apply_async()` calls `run.apply()`, then checks `run.status`. If `WAITING_RESULTTASKS` and not all referenced calls have ended → parks the parent call in `WAITING_SUBTASKS_OR_HOOKS`. When the child calls reach `ENDED`, the `RunScheduler` is notified via `taskrun_result_reference_ended()` (line 76), which decrements the wait counter. Once zero → `all_taskrun_result_references_ended()` (line 100) → `TaskRunStateMachine.succeed()`.

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
    taskcall = child_session.add_user_message(prompt)
    return {"result": taskcall, "session_pk": child_session.model.pk}
```

The `taskcall` is an `AgentTaskCall`. When the parent receives this dict, the framework serialises it, finds the `AgentTaskCall` ref, enters `WAITING_RESULTTASKS`, waits for the subagent's entire chain to resolve, then transparently substitutes the `AgentTaskCall` with the final `Message`. The parent never blocks in its own code — it just returns the call and the framework handles the rest.

---

## Direct LLM Call (`llm_query` / `call_llm_direct`)

Agents sometimes need a lightweight LLM judgment — classification, a rewrite, a small decision — without spawning a subsession or polluting the current turn's context. The `llm_query` **tool** (`.agentone/scripts/core/call_llm_direct.py`, registered in `.agentone/scripts/core/scripts.md`) covers this: input in, result out, no separate agent session.

### Tool vs task split

- `llm_query(messages, model)` is the LLM-facing **tool**. It accepts a plain string, a list of strings, or OpenAI-format `{"role", "content"}` dicts (`system`/`user`/`assistant` only; `message` accepted as an alias for `content`), normalises them, and dispatches the task — returning the `AgentTaskCall` so the turn auto-awaits it (see Auto-Await above).
- `call_llm_direct(messages, model_name)` is the bound **task** that does the work: resolve model → build ephemeral session + `Query` → run the existing `call_llm` pipeline synchronously → return a result dict.

The split exists so failures behave correctly: the task carries `max_retries: 3`, and `RateLimitError` is re-raised (never swallowed) so the run parks as `RATE_LIMITED` with auto-resume instead of failing. Any other error returns `{"status": "FAILURE", "error": ...}` for the LLM to react to.

### Ephemeral session

The task creates an inactive `SessionModel` (`SUBTASK_DELEGATE`) + `SessionVersionModel` + `SettingsModel` purely to host the `Query`/`Response` records. It reuses the caller's agent (so `call_llm` task allow-lists resolve), pins `latest_session_version` so `Session(model)` resolves, and sets `tool_call_syntax=CUSTOM` since a direct call takes no tools. This isolates the call from the caller's in-flight turn, which forbids a second WAITING/ACTIVE query on the same session version (`build_llm_context.py:48`).

### Model fallback

Explicit `model` → caller's model (`session.aimodel`) → user's Default Model setting. No model anywhere returns a `FAILURE` dict instead of calling.

### Result contract

```python
{"content", "model", "prompt_tokens", "completion_tokens",
 "cached_tokens", "reasoning_tokens", "total_time", "status",
 "session_pk", "query_pk", "response_pk"}  # + "error" on failure
```

---

## Subagent Result Delivery

The `subagentResultDelivery` setting on `SettingsModel` controls how a spawned subagent's final output reaches the parent session:

| Mode | Behavior |
|---|---|
| `passive` (default) | Subagent's result is appended as a template message to the parent conversation, but does **not** trigger the parent's agent loop. The parent must explicitly call `await_subsession` or `message_subsession`. |
| `immediate` | Subagent's result is injected into the parent conversation **and** triggers `process_turn` on the parent — the parent processes the result as a new user input. |

Both modes use the same `ingest_subagent_result` background task (always dispatched by `delegate_task(blocking=False)`, `spawn_subtask(blocking=False)`, or `start_subsession`). The difference is only whether the function chains to `process_turn` at the end:

```python
def ingest_subagent_result(session, child_session_pk, summary, result):
    # Create a template message in the parent conversation
    message = Message.objects.create(...)

    if session.subagentResultDelivery == "immediate":
        return session.get_task("process_turn").delay(message=message)
    # passive: return None — message is appended but no turn triggered
```

### Dependency Resolution via `WAITING_DEPENDENCY`

The critical design question: **how do the async tools (`delegate_task(blocking=False)`, `spawn_subtask(blocking=False)`, `start_subsession`) remain non-blocking while `ingest_subagent_result` needs the child's result?**

The answer is the framework's argument-dependency mechanism, built into `AgentTaskCall`:

```
delegate_task(blocking=False)  (or start_subsession / spawn_subtask / message_subsession):
  1. child_task = child.get_task("ingest_user_message").delay(parts=parts)
  2. session.get_task("ingest_subagent_result").delay(result=child_task)
                                         ▲
                                    AgentTaskCall passed as argument
```

Step 2 passes `child_task` (an `AgentTaskCall`) as the `result` argument. During `AgentTaskCall.create()`, the following happens:

**`create_call_arguments_json()`** (`agent_task_call.py:259`) serialises the arguments. For `AgentTaskCall` objects it:
1. Stores `{"_type": "AgentTaskCall", "pk": child_task.pk}` in `carguments_json`
2. Appends `child_task.pk` to `ref_pks` — this populates the `taskcall_arg_references` M2M on the new call

**`CallScheduler._apply_async()`** (`call_scheduler.py:22`) then checks:

```python
if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
    return  # Still waiting — park in WAITING_DEPENDENCY
```

Since `child_task` hasn't ended yet (it was just created in step 1), the delivery call enters `WAITING_DEPENDENCY` and **does not proceed**. The parent's tool call returns immediately — it never blocks.

**`on_arg_reference_task_ended()`** (`call_scheduler.py:46`) fires when `child_task` reaches `ENDED_STATUS`. It checks whether all references have resolved:

```python
if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
    return  # Still waiting for other arguments
CallScheduler.on_all_arg_reference_tasks_ended(task_call_id)
```

Once all deps are met, `start_new_taskrun()` (`call_scheduler.py:121`) creates the `AgentTaskRun` for the delivery call. **At this point** `child_task.taskcall_result_run` is set, so `_create_run_arguments_json()` (`agent_task_run.py:250`) converts the `AgentTaskCall` ref into an `AgentTaskRun` ref, and `_resolve_run_arguments(timeout=0)` resolves immediately because the referenced run has already ended.

### Flow Diagram

```
delegate_task(blocking=False)  (or start_subsession / spawn_subtask / message_subsession)
  │
  ├─ 1. child.get_task("ingest_user_message").delay(parts)
  │       └── AgentTaskCall(child_task) created, run queued
  │
  ├─ 2. session.get_task("ingest_subagent_result").delay(result=child_task)
  │       └── AgentTaskCall(delivery) created
  │             └── taskcall_arg_references += child_task
  │             └── _apply_async() → WAITING_DEPENDENCY (child not done)
  │
  └─ 3. return {"session_pk": ..., "mode": "passive|immediate"}
        └── parent continues its turn immediately
                │
                ▼  (async, in Celery)
        child_task runs to completion
                │
                ▼
        child_task → ENDED_SUCCESS
                │
                ▼
        on_arg_reference_task_ended(delivery.pk, ...)
                │
                ▼
        all deps resolved → on_all_arg_reference_tasks_ended(delivery.pk)
                │
                ▼
        start_new_taskrun(delivery.pk) → AgentTaskRun created
                │
                ▼
        _resolve_run_arguments(timeout=0) → child result ready → func runs
                │
                ▼
        ingest_subagent_result(session, child_session_pk, summary, result)
                │
                ├─ passive: create template Message, return None
                │
                └─ immediate: create Message + chain to process_turn
                              └── parent processes subagent output
```

### Comparison: `delegate_task(blocking=True)` vs async delegation

| Aspect | `delegate_task(blocking=True)` | `delegate_task(blocking=False)` / `start_subsession` / `spawn_subtask` |
|---|---|---|
| **Blocking** | Yes — returns `child_task` in result dict, framework auto-awaits via `WAITING_RESULTTASKS` | No — returns immediately, delivery is a background task |
| **Result delivery** | Via auto-await — parent's **current** turn sees the result as tool output | Via `ingest_subagent_result` background task — result is injected as a **new** user message in the conversation |
| **`subagentResultDelivery`** | Unaffected — always blocks regardless of setting | Affected — setting controls whether `process_turn` is triggered after delivery |
| **Use case** | Parent needs the subagent's result to complete its current turn | Parent delegates work and continues; result arrives asynchronously |

---



## UI rendering (webui, current)

The primary UI is `webui/` (Django templates + htmx + SSE), with per-tab events over `/app/ws/events/` and component refetching driven by observable keys. The legacy pyHtmlGui/WebSocket UI has been removed.

See: [`ui-rewrite.md`](ui-rewrite.md), [`observables-migration.md`](observables-migration.md), [`htmx-sse.md`](htmx-sse.md), [`ui-implementation-guide.md`](ui-implementation-guide.md).


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
| `runtime/workspace_access.py` | 175–215 | `resolve_policy()` |
| | 296–394 | `evaluate()` |
| | 397–409 | `task_access_posture()` |
| | 412–437 | `extract_path_args()` |
| | 449–522 | validation (`validate_workspace_access` / `validate_agent_access`) |
| `runtime/guardrails.py` | — | `check_shell_paths` / `check_python_paths` path analysis; `_shell_targets` whitelist-based classifier |
| `runtime/tasks/bound_task.py` | 196–245 | `_filesystem_access_block()` |
| | 247–273 | `_ensure_private_dir_on_access()` |
| `runtime/tasks/call_scheduler.py` | 222–264 | `_guardrail_filesystem_check()` |
| `runtime/session/session.py` | 84–99 | `private_dir` / `ensure_private_dir()` |
| | 545–585 | `get_task()` / `get_tool()` |
| | 990–1040 | `add_user_message()` / `_prepare_inbound()` / `_resolve_inbound_task()` |
| `.agentone/agents/baseagent/scripts/ingest_user_message.py` | 14–50 | `ingest_user_message()` |
| `.agentone/agents/baseagent/scripts/decide_next_step.py` | 19–62 | `decide_next_step()` |
| `.agentone/agents/baseagent/scripts/scripts.md` | 35–42 | `process_turn` CHAIN definition |

### UI (webui)

| File | Content |
|---|---|
| `webui/core/components.py` | Component registry, render modes, ETag/cache, placeholders |
| `webui/core/events.py` | Per-tab event socket (`/app/ws/events/`) and watch handling |
| `webui/core/layout.py` | Page shell/layout helpers |
| `webui/features/chats/*` | Chat page, components, sidebar integration |
| `webui/static/webui/ws-events.js` | WebSocket/EventSource shim for htmx SSE triggers |
| `webui/static/webui/app.js` | Client watch-set sync, component fetch behavior |

---

**See also:** [Architecture](architecture.md) · [Manifest format](manifest-format.md) · [Development guide](development.md) · [User guide](user-guide.md)
