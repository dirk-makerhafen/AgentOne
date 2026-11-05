# AgentOne — Code Review (November 2026)

**Scope:** correctness bugs and logical errors in `server/`, `runtime/`, `registry/`,
`ui/`, `api/`, `config/` and `launcher/`. Stylistic nits are only included where
they hide a defect or actively mislead.

**Method:** targeted reading of the hot paths (task dispatch, state machines,
data collections, work items, cron, browser daemon, session settings, UI
realtime layer), plus the existing test suites. Every finding below was
verified against the source; where a test reproduces the bug, the test name is
cited.

**Tree state:** the review was run on a dirty working tree that already
contained in-progress work (provider/model probe: `runtime/test_run.py`,
`runtime/final_result.py`, `server/tasks/probe_model.py`,
`server/tests/test_test_run.py`, migration `0171`, right-panel/test-button UI
changes). Findings that concern that in-progress work are marked **[new]**.

---

## 0. Summary

| Severity | Count | Theme |
|---|---|---|
| **P0** — breaks a shipped feature or loses user work | 5 | probe smoke test crashes *(fixed)*; a turn can be silently cancelled *(fixed)*; cron never runs *(fixed)*; all tools can vanish on reload *(fixed)* |
| **P1** — wrong behaviour under realistic conditions | 14 | work-item reopen/resume, data-flow reprocessing, browser tab targeting/timeouts, UI event loss, dispatch options dropped |
| **P2** — correctness or safety gaps with narrower reach | 13 | session/agent settings inheritance, call-scheduler edge cases, browser path/ownership, API/config posture |
| **P3** — hygiene, dead code, misleading debug output | 12 | `display:none1`, `/tmp` logging, root-logger DEBUG, stale tests |

Plus one **blocking build defect** (import cycle, §1.1) that was already fixed
because the test suite would not collect without it.

**Six fixes are now applied.** §1.1 was fixed during the review because the
test suite would not collect without it; the user-visible P0s (§1.2, §1.3) and
the silent-subsystem-loss issues (§1.4, §1.5, §1.6) were fixed afterwards.
Everything else is reported, not changed.

---

## 1. Blocking issues

### 1.1 Import cycle `server.models` ⇄ `server.tasks` — *fixed*

`pytest --collect-only server/tests/` failed to import the test tree:

* `server/models/sessions/session_version.py` imported `runtime.session.session.Session`
  at module level, which imports `server.models...`, which imports
  `server.models.tasks.agent_task_call`, which imported
  `server.tasks.task_dispatcher`, which imports the world.

**Applied fix:** `SessionVersionModel.get_runtime()` now does a local
`from runtime.session.session import Session` (line 57-60), and
`server/models/tasks/agent_task_call.py` no longer imports `celery_delay`
(it was unused in that module). With those two edits the suite collects
1,601 tests.

**Follow-up worth doing:** add an import-cycle regression test (import
`server.models` in a clean interpreter) — the cycle will otherwise creep back.

### 1.2 **[new]** Provider/model smoke test raises `AttributeError` on every run — P0 — *fixed*

`runtime/test_run.py:136-138` and `:176` test the call status against

```python
TaskCallStatus.FAILED
TaskCallStatus.CANCELLED
TaskCallStatus.RATE_LIMITED
```

`TaskCallStatus` only defines `NEW / WAITING / ACTIVE / HALTED / ENDED`
(`server/models/enums/task_enums.py:35-42`). The tuple at line 135-139 is
evaluated on the **first** iteration of the wait loop and is *outside* the
`try` block, so `run_model_test()` dies immediately with
`AttributeError: FAILED`.

`server/tasks/probe_model.py` catches it and stores a generic
`verdict=failed / error_kind=exception`, so the UI reports “model failed”
for every provider — a false negative that looks like a real outage.
`server/tests/test_test_run.py` passes only because it mocks
`run_model_test`.

**Applied fix:** `runtime/test_run.py` now waits only for
`TaskCallStatus.ENDED` and derives the verdict from `status_detail`
(`ENDED_SUCCESS` / `ENDED_FAILURE_EXCEPTION` / `ENDED_FAILURE_LOGIC` /
`ENDED_CANCELLED` / `ENDED_STOPPED` / `WAITING_RATELIMIT`), preferring the
provider-level detail recorded on the latest `Response`. The wait loop reuses
the freshly-read call row for `get_result()` instead of the stale local
object. A regression test (`server/tests/test_test_run.py::SmokeTestVerdictTest`)
drives the runner through an `ENDED_FAILURE_EXCEPTION` call and would have
raised `AttributeError` before the fix.

### 1.3 `AgentTaskRun.create` returns `None`, and the scheduler silently cancels the turn — P0 — *fixed*

`server/models/tasks/agent_task_run.py:109-112`:

```python
if task_type == TaskType.TASK:
    t = session.get_task(task_name)
    if not t:
        return None
```

`CallScheduler._pick_up_and_create_run` may return `None`; the caller
(`runtime/tasks/call_scheduler.py:978-999`) then *cancels* the call so that
dependents unblock. The comment explains the intent, but the user-visible
effect is:

1. a stale/version-pinned session whose agent no longer exposes `call_llm`
   can never answer;
2. the query is flipped back to `WAITING` by recovery, then re-dispatched,
   then cancelled again;
3. 15 minutes later `_recover_stale_queries` marks the query **SUCCESS** with
   no response (`server/tasks/recovery_scheduler.py:926-948`).

So the user's message disappears with no error anywhere in the UI.

**Reproduced by**
`server/tests/test_recovery_scheduler.py::StaleQueryLivenessTest::test_resumes_query_with_stale_response`
(now passes: a non-ended `call_llm` call exists after recovery).

**Applied fix:**

* `AgentTaskRun.create` falls back to `AgentTaskCall.task_definition_version`
  when the live session scope no longer exposes the task, so version-pinned
  sessions keep answering. A call with no resolvable task/definition returns
  `None` instead of raising.
* `CallScheduler._pick_up_and_create_run` returns a `_TaskUnavailable` sentinel
  when a run truly cannot be created (distinct from a lost `pick_up()` race,
  which still returns `None`).
* `start_new_taskrun` fails such a call with `ENDED_FAILURE_EXCEPTION`
  (`TaskCallStateMachine.fail_unavailable`, new
  `ACTIVE_QUEUED → ENDED_FAILURE_EXCEPTION` transition) instead of cancelling
  it. If the call references a `Query`, that query is set to `FAILURE` and a
  failure `Response` (`error_type="task_unavailable"`) carries
  `"task '<name>' is not available in this session's agent"` to the chat UI.
* Regression coverage: `server/tests/test_call_scheduler_unavailable.py`.

### 1.4 Registry: one empty `scripts.md` disables every tool in the scope — P0 — *fixed*

`registry/loader/load_scripts_manifest.py:62-67`:

```python
if len(manifest.keys()) == 0:
    if len(manifest_path.read_text().strip()) == 0:
        return []        # ← aborts the whole loader
```

`return []` inside the `for manifest_path in scripts_dir.rglob("scripts.md")`
loop:

* skips every manifest that would have been collected after this one;
* skips both loading passes entirely;
* leaks the `ScriptsGeneration` row allocated at line 54 (created before the
  loop, never used).

For global scripts (`~/.agentone/runtime/...` + upstream merge) this can make
*all* tools disappear after a reload, with no log line. An empty `scripts.md`
is realistic after a bad merge or an upstream sync.

**Applied fix:** an empty `scripts.md` is skipped with a warning that names the
file, and the `ScriptsGeneration` row is created only after collection
succeeds. Regression test:
`server/tests/test_loader.py::LoadScriptsTwoPassTest::test_empty_manifest_is_skipped_not_fatal`.

### 1.5 Cron: jobs created through the API never run — P0 — *fixed*

`Cronjob.next_run_at` defaults to `NULL` (`server/models/cron.py:57`).
`Cronjobs.due()` filters `next_run_at__lte=now`
(`runtime/cron/crons.py:80-88`), so a `NULL` row is never due.

* `runtime/cron/crons.py:118-126` (`Crons.create`) computes `next_run_at` —
  but the HTTP path does not go through it.
* `api/serializers/cron.py:42-48` (`CronWriteSerializer`) exposes no
  `next_run_at` and no `message`; `api/views/cron.py:13-30` is a plain
  `ModelViewSet`, so `POST /api/v1/cron/` creates a job that will never fire
  *and* has an empty message.
* `Crons.update()` (`runtime/cron/crons.py:129-134`) does a plain `setattr`
  loop + `save()`, so editing the schedule leaves the old `next_run_at`
  (possibly already in the past → immediate run, or months away → no run).

`api/tests/test_cron.py::test_create_cron` asserts only `201` + row existence,
which is why this is green.

**Applied fix:** `Cronjob.save()` is now the single choke point. It derives
`next_run_at` for new/active/re-scheduled jobs and clears it when `is_active`
flips to false. `CronWriteSerializer` accepts a text/JSON `message`, builds it
through `build_cron_message()`, and defaults `is_active` to true (DRF treats a
missing multipart boolean as false). Regression tests:
`api/tests/test_cron.py::TestCron` and
`server/tests/test_cron.py::CronjobModelTest`.

### 1.6 Cron: human-friendly schedules are dead code; failures re-fire every minute — P0/P1 — *fixed*

`runtime/cron/execute.py:94-124` defines `_expand_shorthand` plus
`compute_next_run`. **Neither is called anywhere** — `Crons._compute_next_run`
(`runtime/cron/crons.py:86-91`), the manifest loader
(`registry/loader/load_cron_manifest.py:76`) and the execution path
(`runtime/cron/execute.py:76`) all call raw `croniter` on the unexpanded
string.

Consequences:

* `schedule: "every 15 min"` → `croniter` raises → loader stores
  `next_run_at = None` → the job *never* runs. `Crons.create` stores
  `next_run_at = None` for the same input. Only standard cron syntax works,
  despite the docs.
* On failure, `execute_cron_job` writes `last_status="error"` but never
  advances `next_run_at` (`runtime/cron/execute.py:85-88`), so the job stays
  due and is retried **once per minute forever** with no backoff.

**Applied fix:** `runtime/cron/schedule.py` now holds the single
`expand_shorthand()` / `compute_next_run()` implementation, used by the model,
loaders, API and executor (`runtime/cron/execute.py` still re-exports it for
existing callers). `execute_cron_job()` advances `next_run_at` on failure too,
so a failing job follows its schedule instead of retrying every minute; an
invalid schedule parks it (`next_run_at=None`).

The related loader bug is also fixed: `is_active` is now reconciled from the
manifest and `next_run_at` is no longer rewritten on every reload (it is
derived only when missing, created, or re-scheduled).

Regression tests: `server/tests/test_cron.py::CronExecuteTest` and
`server/tests/test_cron_content.py::CronFileRoundTripTest`.

---

## 2. High severity

### 2.1 `agent_settings is None` crashes setting resolution — P1

`server/models/agents/agent_version.py:292`:

```python
if (value := getattr(self.agent_settings, name)) is not None:
```

`AgentVersionModel.agent_settings` is nullable, and `getattr(None, name)`
raises. Any code path that resolves a setting (`session.priority`, task
instance creation, work-item dispatch…) explodes for an agent version created
without settings.

**Reproduced by** `server/tests/test_workitem.py::WorkItemFsmTest::test_attach_root_task_is_once_only`
(fails at `agent_version.py:292` through `TaskInstance.get_or_create`).

Same class of bug in `resolve_property` (`:396`): `getattr(self, name)` with
no default raises for any property the version does not define.
`collect_system_prompts` already uses a default — that pattern should be
applied everywhere.

### 2.2 Work-item `reopen` and `resume` bounce straight back — P1

`WorkItemStateMachine.reopen` (`runtime/workitems/workitem_fsm.py:419-426`)
moves `done → in_progress` but leaves `root_task` pointing at the **already
ended** executor call. `_report_work_item_outcomes`
(`server/tasks/tick_scheduler.py:880-903`) selects every `in_progress` item
whose `root_task` is terminal and calls `_report_outcome` → `report_success`
→ `blocked`, on the next tick (≤10 s).

The board's `resume` action (`ui/main/workitems/board_data.py:264-267`,
`in_review → in_progress`) has exactly the same problem.

Net effect: clicking **Reopen** silently converts `done` into `blocked` with
the *old* outcome text, and never dispatches anything. The item can only be
recovered via `cancel → mark_ready`.

Fix: `reopen`/`resume` should clear `root_task` and `verify_status` and go to
`ready` (i.e. reuse `mark_ready` semantics), so the dispatcher picks it up
again. `mark_ready` already documents exactly this trap
(`workitem_fsm.py:165-199`) — the terminal-state paths just don't apply it.

### 2.3 Work-item reject budget can increment without a rejection — P1

`reject_or_escalate` (`runtime/workitems/workitem_fsm.py:362-389`):

```python
WorkItem.objects.filter(pk=item_id).update(verify_attempts=item.verify_attempts + 1, ...)
WorkItemStateMachine.reject(item_id, reason)      # may no-op (undecided filter)
return WorkItemVerifyStatus.REJECTED
```

`reject()` is guarded on `_undecided_filter()`. Under a race (two verdicts, a
stale board) the counter increments and “rejected” is returned while nothing
changed; after `MAX_VERIFY_ATTEMPTS` of those the item escalates with a
history that never happened. `ui/main/workitems/board_data.py:253-261` works
around the *symptom* (comparing before/after state) instead of fixing the
FSM.

Fix: do the increment and the transition in one conditional `update()` (or
`select_for_update()`), and return the status that was actually written.

### 2.4 Data-flow reprocessing loses the `source_item` link — P1

`server/tasks/reprocess_collection.py:96-114` collects only
`item.source_call` from stream/set sources and then calls
`_dispatch_processor(collection, call)` — without `source_item=item`, even
though `_dispatch_processor` supports it and uses it for cascade deletion
(`server/tasks/tick_scheduler.py:362-368`, `:524-525`).

Result: after a reprocess, every downstream item has `source_item = NULL`,
so `_cascade_deletion` (`reprocess_collection.py:15-45`) can never find it,
and removing an upstream item leaves stale rows downstream forever.

### 2.5 API `reprocess` runs the wrong function — P1

`api/views/collections.py:39-48`:

```python
from server.tasks.tick_scheduler import _propagate_from_collections
_propagate_from_collections(collection)
```

`_propagate_from_collections` only looks at `CollectionItem` rows created in
the **last 30 seconds** (`server/tasks/tick_scheduler.py:714-722`), so the
“Reprocess” button is a no-op for any existing collection. The real worker is
`server/tasks/reprocess_collection.reprocess_collection(name)` (a Celery
task), which is never called from the API.

### 2.6 Data-flow members derived from the processor result never materialise in production — P1

`_dispatch_processor` computes `pre_member = _extract_member(flow, None, call)`
from the **source call's arguments**, stores a dedup token, dispatches, then
immediately reads back the call:

```python
processor_call.refresh_from_db()
if processor_call.status_detail == ENDED_SUCCESS:   # server/tasks/tick_scheduler.py:488
```

In production the processor is dispatched asynchronously, so this is always
false. The item is then written with `member = pre_member`, `value =
call.carguments_json`, and is never reconciled when the processor finishes.
So `member_field` / `score_field` expressions that read the result (the
docstring explicitly advertises this, lines 506-509) silently use the source
arguments instead. Sets dedupe and rank on the wrong key, permanently.

Secondary effect: in eager mode (tests, `CELERY_TASK_ALWAYS_EAGER`) the token
is deleted when the result-derived member differs, but
`_dispatch_data_flows` dedupes on the args-derived member
(`server/tasks/tick_scheduler.py:689`) — so the same source call is re-dispatched on every 10 s tick,
forever.

Fix: make the final member/score derivation a separate step driven by the
processor call's terminal state (e.g. a small reconciliation pass over recent
`ENDED` processor calls), and dedupe on the processor call, not on a
provisional member.

### 2.7 UI consumer can drop events (LRANGE/DELETE race) — P1

`ui/consumer.py:66-76`:

```python
result = r.blpop(queue_key, timeout=5)
...
remaining = r.lrange(queue_key, 0, -1)
r.delete(queue_key)
```

Anything pushed between the `LRANGE` and the `DELETE` is destroyed without
being processed. Under load (several model saves in one tick) a chat view
misses messages until a full re-render.

Fix: `LTRIM` by the exact count that was read (`ltrim key N -1`), or use
`LMOVE` to a per-instance “processing” key and delete that afterwards.

### 2.8 **[new]** Duplicate method definitions shadow the new probe implementation — P1

`ui/main/rightpanel/provider/rightpanel_provider.py` defines the same three
methods twice:

| method | first (probe-based) | second (legacy, wins) |
|---|---|---|
| `_resolve_session` | 193 | 292 |
| `test_provider` | 222 | 316 |
| `test_model` | 245 | 325 |

Python keeps the **last** definition, so the template added in this
working tree (`{% if pyview._probe … %}`, lines 78-92) never sees a
`_probe` state: `test_provider()` runs `_run_test()` → `call_llm_direct`,
and the “testing…” spinner / result line never appears.

`ui/main/rightpanel/model/rightpanel_model.py` has the same duplication for
`test_model` (`:197` probe version, `:296` legacy).

Note the shadowed legacy `test_model(provider_id)` signature is also
confusing (the template passes a model id in one place, a provider id in the
other). Fix: delete the legacy block(s) and the duplicated `_resolve_session`.

### 2.9 Browser: `screenshot` is not a known action — P1

`runtime/browser/actions.py:13-14` lists

```python
READ_ONLY_ACTIONS = {status, snapshot, read, tabs, cookies, wait, close_tab}
MUTATING_ACTIONS = {open, navigate, click, type, back, evaluate, upload, download}
```

`ALL_ACTIONS` therefore omits **`screenshot`**, even though
`Daemon._action_screenshot` exists (`runtime/browser/daemon.py:333`), the tool
docstring documents it (`.agentone/scripts/browser/browser.py:19`, `:74`), and
`runtime/browser/snapshot.py:13` points at it. `browser(action="screenshot")`
returns `unknown action 'screenshot'`.

Add it to `MUTATING_ACTIONS` (it writes a file) or `READ_ONLY_ACTIONS` (it does
not touch server state) — the docs say writes are mutating.

### 2.10 Browser: a missing page silently retargets to the last tab — P1

`runtime/browser/daemon.py:188-197`:

```python
for candidate in binding.context.pages:
    if getattr(candidate, "_agentone_page_id", None) == rec.page_id:
        return candidate
# Fallback: the registry is the source of truth, so trust the last page.
return binding.context.pages[-1]
```

If the registry still knows a page id but the live context page is gone
(user closed the tab, page crashed), every action (`click`, `type`,
`evaluate`, `upload`) is executed on **an unrelated tab**. There is no
ownership check on the fallback either, so a child session can end up acting
on another session's tab.

Fix: raise `BrowserError("page is gone — open a new tab")` and prune the
registry record.

### 2.11 Browser: unbounded `wait` / `evaluate` wedge the whole daemon — P1

* `_action_wait` (`runtime/browser/daemon.py:315-325`) passes
  `params["ms"]` straight to `page.wait_for_timeout()` with no cap.
* `_action_evaluate` (`:371-377`) calls `page.evaluate(script)` with no
  timeout, so `while(true){}` blocks forever.

All actions run on **one** driver thread (`_submit`, `:143-151`). The HTTP
request times out after 180 s and returns an error, but the job keeps running
and every subsequent browser action from every session queues behind it.
A single tool call can take the browser capability down until the daemon is
killed.

Fix: clamp `ms` (e.g. ≤ `action_timeout`), wrap `evaluate` in a
`page.wait_for_function`-style bound or run it in a throwaway context, and
have `_submit` mark the daemon unhealthy / restart the driver thread on
timeout.

### 2.12 `BoundTask.apply_async` silently discards dispatch options — P1

`runtime/tasks/bound_task.py:432-470` accepts `countdown`, `eta`, `expires`,
`retry`, `time_limit`, `soft_time_limit` and `priority`, documents them, and
then calls

```python
task_instance = self.instance()
return task_instance.apply_async(args=args, kwargs=kwargs, **options)
```

— none of the named parameters is forwarded (only `**options`). They are
also not passed to `self.instance()`, which is called with no args, so the
`TaskInstance` dedupe key ignores the call's arguments.

Callers that schedule with `countdown=`/`time_limit=` get an immediate,
untimed dispatch. Either forward them (`**{...}`) or delete the parameters so
callers stop believing they work.

### 2.13 Terminal allowlist bypass through wrappers — P1

`runtime/terminal/allowlist.py:69-84` resolves only the **first** token and
treats a recognized-but-unapproved agent CLI as requiring approval.
`sudo claude`, `nohup claude …`, `bash -c "claude …"`, `env X=1 claude`, and
`xargs claude` all resolve to a harmless-looking first token and bypass
`unapproved_agent_cli()`.

This is called out as a `first_token` helper — the guard needs to unwrap the
common launchers (`sudo`, `env`, `nohup`, `time`, `command`, `xargs`,
`sh -c`, `bash -c`, `zsh -c`) before deciding, and then treat anything it
cannot classify as an agent CLI as “ask”.

### 2.14 Call scheduler edge cases — P1

Three independent defects in `runtime/tasks/call_scheduler.py`:

1. **Stopped dependency reported as cancelled** (`:78-83`, `:1276-1281`):
   when a required call ends `ENDED_STOPPED`, dependents are failed with
   `ENDED_CANCELLED`. The UI then says “cancelled” for a user stop, and any
   retry policy keyed on stop-vs-cancel misbehaves.
2. **One missing hook aborts the rest** (`:1248-1252`):
   ```python
   for i, hook_instance in enumerate(after_hooks):
       if not hook_instance:
           return      # kills the remaining hooks *and* the state update below
   ```
   `call.taskcall_after_run_hooks.set(...)` and the `apply_async()` loop are
   skipped, leaving the call in `WAITING_SUBTASKS_OR_HOOKS` until recovery.
   Should `continue` (and record the gap).
3. **`_cancel_safe` fallback always raises** (`:1485-1536`): the “safe”
   wrapper re-raises after logging, so every caller's error handling is
   defeated. It should return `False`.

---

## 3. Medium severity

### 3.1 Session setting resolution mutates cached state — P1/P2

`runtime/session/session.py:1066-1075`:

```python
if isinstance(session_settings_value, (list,)):
    if "+" not in session_settings_value:      # overwrite parent list
        return session_settings_value
    idx = session_settings_value.index("+")
    session_settings_value[idx:idx+1] = self.agent.get_agent_setting(name)
```

* The list is the **JSONField value on the loaded `SettingsModel` instance**;
  it is mutated in place. Every later read of `self.agent_settings` /
  `session_version.session_settings` sees the merged list, so a subsequent
  copy-on-write save (`_set_session_setting`) persists a setting the user
  never chose, and the `+` marker is gone.
* If the agent has no value for `name`, `get_agent_setting` returns `None` and
  the slice assignment raises `TypeError`.

Fix: `return [*value[:idx], *(agent_value or []), *value[idx+1:]]` on a copy.

### 3.2 Copy-on-write setters mutate the live model object — P2

`runtime/session/session.py:1081-1105`:

```python
new_session_setting = session_version_model.session_settings
...
new_session_setting.pk = None
new_session_setting.save()
session_version_model.pk = None
session_version_model.created_at = None
session_version_model.version_number += 1
session_version_model.save()
print(...)         # lines 1094, 1104
```

* The objects being “copied” are the ones already attached to
  `self._pinned_session_version` / `latest_session_version`. After the call the
  in-memory wrapper points at a version whose `.pk` is the *new* row while
  `self.model.latest_session_version` is re-saved separately — any other
  reference to the old object now silently reads the new version's id.
* No `transaction.atomic()`, no `update_fields`.
* Two debug `print()`s (plus the `raise Exception("foo23")` type check at
  line 61) in a hot path.

Fix: build a fresh `SettingsModel()` / `SessionVersionModel()` with the
copied fields (the existing `clone_settings()` helper does exactly this for
agents), inside a transaction.

### 3.3 List inheritance loses siblings with more than one parent — P2

`server/models/agents/agent_version.py:307-311`:

```python
if isinstance(value, (list,)) and extend_at_index is not None:
    value[extend_at_index : extend_at_index + 1] = ext_value
```

After the first parent replaces the `"+"` marker, `value` no longer contains
`"+"`, but `extend_at_index` is still set, so the second parent **overwrites**
the element at that index instead of appending. `child = ["a", "+"]`,
`parent1 = ["b"]`, `parent2 = ["c"]` → `["a", "c"]` (b lost).

Fix: after the first substitution, `value.extend(ext_value)`; the same bug
exists in the session-level path (§3.1).

### 3.4 Browser path confinement is conditional — P2

`runtime/browser/daemon.py:404-430`: `_safe_path` only enforces
`relative_to(root)` when `root` is truthy. Both `write_root` and `read_root`
are supplied by the *caller* (the tool script), and the daemon trusts them.
Any other client (or a future tool that forgets them) can read/write anywhere
the daemon user can. The daemon should derive the root itself from the scope,
not accept it from the request.

Also in the same area: `_action_download` with no `download_path` never calls
`download.save_as(dest)`, leaving Playwright's temp file behind for the life
of the browser context.

### 3.5 Browser profiles are shared across sessions — P2 (design decision needed)

`runtime/browser/registry.py:89-101`: bindings are keyed by `profile_key`
only. `resolve(..., is_root=True)` (`:166-190`) and `_action_tabs`
(`daemon.py:262-267`) let **any** root session see, click, evaluate in and
close tabs owned by **another** session's root, as long as both use the same
named profile (e.g. `profile="github"`). `scope.py` documents sharing the
*login state*; sharing *live tabs* across chats is a bigger capability and is
not documented as such.

Also: `_enforce_budget` (`registry.py:102-108`) closes the least-recently-used
binding while holding the lock, with no check for an action currently in
flight — a long `evaluate` in another session can have its context closed
under it.

### 3.6 Browser daemon dispatches any `_action_*` method — P2

`runtime/browser/daemon.py:228-232`:

```python
fn = getattr(self, f"_action_{action}", None)
```

`is_known()` is enforced only in the tool script. A direct daemon request
(anyone who can read the `0600` token file) can call `_action_shutdown`
(`:388`), bypassing `ALL_ACTIONS`. Validate against `ALL_ACTIONS` inside the
daemon.

### 3.7 `BoundTask` instance dedupe ignores arguments — P2

`runtime/tasks/bound_task.py:432-470` calls `self.instance()` with no
args/kwargs *before* passing them to `apply_async`. `TaskInstance.get_or_create`
computes `dedupe_hash` from `arguments_json` (`task_instance.py:198-237`), so
every `.apply_async(kwargs=…)` on the same bound task shares one instance
regardless of arguments — and the instance-level argument references
(`taskinstance_arg_references`) are never set from the real arguments.

### 3.8 UI: `_on_orm_event` throws away the published payload — P2

`ui/main/chat/messages/messages.py:229-245` ignores `data` entirely and calls
`_on_message_created(pk, action, {})`. The producer side already computes the
filter context (`prev_message_id`, `session_id`, …) in
`runtime/events.py:_extract_filter_context` and ships it in the message, but
the consumer reconstructs `{}` — so every new message falls back to
“append at the end” (line 275) and then re-reads from the DB.

Combined with the position heuristic (`prev_id` lookup at `:263-274`), an
out-of-order or coalesced batch can display messages in the wrong order until
the next full render.

### 3.9 Debug instrumentation hardcoded to `/tmp` — P2

* `runtime/events.py:46-50` appends every published event to
  `/tmp/agentone_events.log`.
* `ui/main/chat/messages/messages.py:198-206` appends every message-view
  callback (including a stack trace, `:249-251`) to the same file.

No flag, no rotation, no size cap, and the path is not portable (Windows).
Two processes writing the same file without coordination. This is
leftover debugging that will grow unbounded on a long-running server.

### 3.10 `runtime/fsobserver.py` forces global DEBUG — P2

`runtime/fsobserver.py:18-19`:

```python
root_logger.setLevel(logging.DEBUG)
fsevents.logger.setLevel(logging.DEBUG)
```

The **root** logger is set to DEBUG at import time (regardless of Django's
`LOGGING`), so every third-party library starts logging debug output. The
`TESTS = '''…'''` blob at lines 22-45 is a pasted fsevents log dump (with the
developer's home paths) that should not be in the tree.

### 3.11 `eval()` "sandbox" is escapable — P2

`server/tasks/tick_scheduler.py:547` and `:567`:

```python
eval(expr, {"__builtins__": {}}, {"item": item})
```

`{"__builtins__": {}}` is a known non-sandbox: `item.__class__.__mro__[1]
.__subclasses__()` reaches `subprocess.Popen`. The expression comes from a
manifest (`member_field` / `score_field`), which is admin-authored, so this is
not remote code execution — but it is one YAML file away from full code
execution and the comment implies safety. Prefer `ast.literal_eval`-style
whitelisting, or at least `getattr(item, …)` with a restricted accessor.

### 3.12 API/config posture — P2

* `config/settings.py:17-18` hardcodes `SECRET_KEY` and
  `AGENT_SERVER_SECRET_KEY` to `'…change-me-in-production'` with no startup
  check. A production deployment that forgets `settings_local.py` signs
  sessions/JWTs with a public value.
* `:20-21` `DEBUG = True` and `ALLOWED_HOSTS = ["*"]` unconditionally.
* `:24` `SESSION_COOKIE_AGE = 99 days`.
* `api/views/sessions.py:81-90` swallows **all** setting errors:
  ```python
  try: getattr(rt, method_name)(data[field])
  except Exception: pass
  ```
  A rejected value (bad reasoning effort, unknown model) returns `200` with
  the old setting, so the UI shows a value that was never saved.
* `api/permissions.py:IsOwnerOrReadOnly` is unused; every model viewset is
  `IsAuthenticated` with a global queryset, so any authenticated user can
  mutate/delete any agent, session, cron or collection. Fine for a
  single-user install, but worth an explicit decision + docs.

### 3.13 Data-collection `name` is globally unique — P2

`server/models/collections/data_collection.py:26` uses
`unique=True` on `name`, while projects/workspaces are first-class scoping
concepts everywhere else. Two projects cannot both define a `todos` stream,
and `reprocess_collection()` / `_propagate_from_collections()` look collections
up by bare name (`DataCollection.objects.get(name=collection_name)`), so a
name collision would silently pick the wrong project's collection.

---

## 4. Low severity / cleanup

| # | Where | Issue |
|---|---|---|
| 4.1 | `ui/main/chat/**` (12 occurrences) | `style="display:none1"` — invalid CSS value, so the element is **not** hidden: `messages.py:55`, `chat.py:57`, `mobileconfig.py:24/30/36/38`, `cards/approval.py:27`, `composer/footer.py:68`, `banner/update.py:15/16/21`. `composer/footer.py:45` also carries two `style=` attributes (`display:none` then `display:none1`). |
| 4.2 | `ui/overlay/appdialog.py:5` | `DOM_ELEMENT_EXTRAS = 'style="display:none" style="display:none" aria-hidden="true"'` — duplicated attribute. |
| 4.3 | `runtime/tasks/call_scheduler.py` | ~40 `print()` debug statements left in the dispatch path (lines 50, 55, 76, 83, 87, 123, 138, 156, 161, 208, 260, …). Replace with `logging` at DEBUG or drop. |
| 4.4 | `runtime/session/session.py:61` | `raise Exception("foo23")` for a type check. Use `TypeError` with a real message. |
| 4.5 | `runtime/session/session.py:512-517` | `except Exception as e: print("Failed to update", e)` — swallows DB errors in `reset_unattended_turn_count`. |
| 4.6 | `runtime/cron/execute.py` vs `runtime/cron/crons.py` | Two `_expand_shorthand`/`compute_next_run` implementations (one dead) — see §1.6. |
| 4.7 | `runtime/fsobserver.py:22-45` | Pasted debug log blob in a string constant. |
| 4.8 | `server/tests/test_workitem.py:403` | Stale path `.agentone/agents/work_verifier/scripts/workitem_verdict.py`; the agent lives at `.agentone/agents/internal/work_verifier/…`. 17 tests error with `FileNotFoundError`. |
| 4.9 | `.agentone/scripts/{core,todo,wiki}/test_*.py` | Three modules import their sibling by bare name (`from wiki_find_unlinked_raw import …`), so `pytest .agentone/scripts/` aborts at collection. Add `conftest.py` with `sys.path` injection or use package-relative imports. |
| 4.10 | `server/tests/testproject/workspace/test-reports/*.md` | Running the test suite **rewrites committed files** (`git status` shows 11 modified reports after a test run). Either gitignore them or write to a temp dir. |
| 4.11 | `runtime/test_run.py:_pick_test_agent` **[new]** | The fallback `return agent` returns *any* agent with a version, even one that does not advertise `final_result` — contradicting the docstring and guaranteeing a `no_tool_call` verdict on that path. |
| 4.12 | `server/tasks/probe_model.py:32-37` **[new]** | The dedup branch returns `{"verdict": "running", "model_pk": …}` with no `model` key, so the template's `pyview._probe.model` renders empty. |

---

## 5. Positive observations

* The task/run FSMs (`runtime/tasks/call_fsm.py`, `run_fsm.py`) are consistently
  guarded with conditional `update()` calls and return `False` on lost races;
  this is the right shape and most of the scheduler follows it.
* The browser capability's tests are green (74 passed) and the scope derivation
  (`runtime/browser/scope.py`) correctly refuses LLM-supplied scope keys.
* `runtime/workspace_access.py` has a clear, documented precedence
  (`deny > ask > allow > default`) and handles symlinks via `resolve()`.
* `api/` is green (249 passed, 6 skipped) and the serializers are careful about
  not leaking secrets (`browser.cookies` returns names/domains only,
  `ProviderSerializer` masks keys).
* Work-item docs (`docs/work-items.md`) are unusually precise; several of the
  bugs above are cases where the code deviated from its own documentation.

---

## 6. Verification log

| Command | Result |
|---|---|
| `pytest server/tests/ --collect-only -q` | 1601 tests collected |
| `pytest api/tests/ -q --reuse-db` | 249 passed, 6 skipped |
| `pytest server/tests/test_browser_*.py -q --reuse-db` | 74 passed |
| `pytest server/tests/test_cron.py server/tests/test_dc_reprocess.py -q --reuse-db` | 36 passed |
| `pytest server/tests/test_test_run.py server/tests/test_messages_ui.py -q --reuse-db` | 16 passed (after the two import fixes) |
| `pytest server/tests/test_test_run.py server/tests/test_call_scheduler_unavailable.py -q --reuse-db` | 8 passed (§1.2 + §1.3 regression tests) |
| `pytest server/tests/test_recovery_scheduler.py -q --reuse-db` | 15 passed (§1.3 fixed) |
| `pytest api/tests/test_tasks.py server/tests/test_session_pause.py server/tests/test_rate_limit_card.py -q --reuse-db` | 108 passed |
| `pytest server/tests/test_call_llm_fallback.py server/tests/test_turn_collapse.py -q --reuse-db` | 37 passed |
| `pytest server/tests/test_workitem.py -q --reuse-db` | **18 failed** (§2.1 + §4.8) |
| `pytest .agentone/scripts/ -q` | **3 collection errors** (§4.9) |

The full `server/tests/` run was **not completed**: `test_dc_ordered_sets.py`
spends ~20 s per test and the run exceeded a 120 s budget without a
`pytest-timeout` plugin installed. Remaining files were sampled individually,
so there may be additional failures in the slower suites.

---

## 7. Suggested fix order

1. ~~**§1.2** (probe `AttributeError`) and **§1.3** (silent turn cancel) — user-visible
   failure of a shipped feature.~~ **Done.**
2. ~~**§1.4** (scripts manifest `return []`) and **§1.5/§1.6** (cron never runs /
   retry storm) — silent loss of entire subsystems.~~ **Done.**
3. **§2.1** (`agent_settings is None`) — cheap; also fixes
   `test_workitem.py::test_attach_root_task_is_once_only`. Fix **§4.8** (stale
   verifier path) in the same sitting to unblock the other 17 tests.
4. **§2.2/§2.3** (work-item reopen/resume, reject budget) — the board is
   actively misleading.
5. **§2.4/§2.5/§2.6** (data flows) — one coherent change: pass `source_item`
   through reprocessing, call `reprocess_collection` from the API, and derive
   member/score from the processor call's terminal state.
6. **§2.7** (consumer race) and **§2.8** (shadowed methods) — small, isolated.
7. **§2.9–§2.11** (browser correctness/robustness) — add a watchdog for the
   driver thread first.
8. Everything else opportunistically; §4.10 (tests dirtying the tree) first
   among the low-severity items so reviews produce clean diffs.
