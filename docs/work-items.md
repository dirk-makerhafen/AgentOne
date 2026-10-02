# Work Items — long-term task layer

**Status:** implemented (increment 1) — model, FSM, tick dispatch, agent
verification, agent-facing tool. No UI. See §12 for what was deferred.
**Scope:** increment 1 — model, FSM, tick dispatch, agent verification,
agent-facing tool. No UI.

---

## 1. Problem

The framework has a deep *execution* layer and no *work* layer.

`AgentTaskCall` (one logical invocation) and `AgentTaskRun` (one attempt) are
driven by two coupled state machines with ~20 states, dependency graphs via
arg-references, auto-await, hooks, retries, rate limiting, guardrails and LLM
auto-approval. That is job execution, and it is well built.

What does not exist is any entity representing *a thing someone wants done*.

| Need | Current state |
|---|---|
| Durable work item | Absent. `TaskDefinition` is a code artifact loaded from YAML (`server/models/tasks/task_definition.py:13`). `AgentTaskCall` is an execution record, immutable outside its FSM (`server/models/tasks/agent_task_call.py:374-378`). |
| Work outliving a session | Impossible. Every ATC is bound to a `session_version` and `CASCADE`-deleted with its session. |
| Backlog | Absent. `WAITING_QUEUE` is intra-turn admission control, not a backlog. Nothing promotes items into the pipeline. |
| UI-created work | Impossible. `TaskInstance.get_or_create` (`server/models/tasks/task_instance.py:161`) requires a `TaskDefinitionVersion`; every dispatch originates from a manifest tool, a cron, or an in-conversation tool call. |
| Project scoping of work | `Project` (`server/models/project.py:8`) owns agents, skills, sessions and crons — no tasks. |
| Decomposition | The planner agent produces a textual plan (`.agentone/agents/planner/agent.md:16-42`), not structured child items. |

The target use case: one person, many projects, long-running tasks decomposed
into subtasks, some of which run in parallel on different agents.

### 1.1 Why the existing todo list is not a foundation

`.agentone/scripts/todo/todolist.py` looks like a task layer but is not:

- **No database.** State is reconstructed by replaying the `result_json` of the
  most recent successful `todolist_action` call (`todolist.py:43-62`). It
  therefore inherits the session's lifetime and cannot be shared or queried.
- **`depends_on` is unenforced** — documented as an "informational ordering
  hint" (`todolist.py:203-205`).
- **Three statuses only:** `pending`, `in_progress`, `completed` (`todolist.py:35`).
- Needs a compaction mirror (`.agentone/scripts/compact/ingest_compaction.py:213-214`)
  to survive context loss.

A `WorkItem` stored in the database has none of these problems.

---

## 2. Design principles

### 2.1 The FSMs are self-sufficient; the tick is the only operator

> Every state and error is captured in the normal task state machines. The
> recovery scheduler exists only to clean up after framework-development bugs
> and is **deliberately disabled** (`config/settings.py:83-86`, commented out
> since `38b6fdf`). It is retained as insurance and **must not gain new code**.

Consequences for this feature:

- All dispatch and reporting logic lives in `tick_scheduler.py`, never in
  `recovery_scheduler.py`.
- A stuck work item is fixed by adding a transition to `workitem_fsm.py`, not
  by adding a repair pass.
- `docs/` and `AGENTS.md` must be corrected: `AGENTS.md:84` currently claims
  recovery runs every 60s. It does not.

### 2.2 Two lifecycles, one arrow

The work layer and the execution layer have different time scales and must not
share a state machine.

```
   WorkItem (days → weeks)                AgentTaskCall (ms → minutes)
   ───────────────────────                ─────────────────────────────
   backlog → ready → in_progress          NEW → WAITING_* → ACTIVE_* → ENDED_*
              ↓ blocked / done / cancelled        │
              └──────────── dispatch ─────────────┘
                                    ↑
                    observe terminal state ──┘   (one-way)
```

**The one hard rule: no ATC/Run FSM code may read or write `WorkItem.status`.**
The arrow points one way. The tick observes a terminal ATC and reports in.

This is what keeps a user moving a card from racing the invariants in
`docs/task-state-machines/04-invariants.md` — I1–I6 assume ATCs are
single-writer and append-only. A draggable column cannot be a column in that
FSM.

### 2.3 Turn death semantics must not leak

`tick_scheduler.py:243-246` skips any call older than `TURN_DEATH_AGE`
(24h, `server/tasks/recovery_scheduler.py:46`) to avoid dispatching day-old
turns. That is correct for a turn and **fatal for a backlog**.

The work-item routines must therefore never call `_is_ancient`. A work item
may legitimately sit in `ready` for a month.

---

## 3. Out of scope for increment 1

| Deferred | Note |
|---|---|
| Board UI | ~280 lines of orphaned CSS already exist at `ui/static/css/main.css:3669-3938`; nav buttons at `ui/sidebar/rail.py:57` and `ui/sidebar/sidebar.py:45` are `display:none` and `kanban` is absent from `sidebar.panels` (`ui/sidebar/sidebar.py:108-120`). No panel class, model or migration was ever committed (`git log --all --diff-filter=A`). The design implies a *multi-user* board (assignee, tenant, comment, bulk-action classes) that a single-user scope may not need — reassess before reusing it. |
| Todo list migration | Deferred by decision. |
| Structured result schema | Verification judges free-text output against the requirement. It does not validate against a declared schema — v2 (§13). |
| `recovery_scheduler.py` | Stays disabled and untouched. |
| ATC / Run FSM changes | Invariants I1–I6 remain intact. |
| Bounded auto-requeue | v1.1 (§13). |

### 3.1 A note on `final_result` and false-green

A crashing TOOL or COMMAND is caught in `runtime/tasks/bound_task.py:133-138`
and returned as `(False, {'status': 'exception', 'message': traceback})` — a
normal return value. The run then takes the SUCCESS path
(`server/models/tasks/agent_task_run.py:248-252`).

**This is correct and must not change.** Internal `TaskType.TASK` failures
re-raise and go red. Marking user-facing tool errors as `FAILURE` would trigger
`schedule_retry`, re-running the same bad arguments from the same agent, and
would paint ordinary conversational correction red in the UI.

ATC `SUCCESS` means *invoked and produced a result*. Goal-level judgement
belongs on the work item, not the call.

### 3.2 The trap this creates for verification

A verifier that reasons from `root_task.status == ENDED_SUCCESS` will approve
failed work. The ATC is green precisely when a tool crashed (§3.1), and the
verifier has no way to distinguish "ran and succeeded" from "ran and threw a
traceback" without reading the result payload.

Two rules follow, and they are load-bearing:

1. **The brief must carry the result payloads, not the ATC status.** The
   reviewer sees what the executor actually produced. `status_detail` is
   included only as a routing hint, explicitly labelled unreliable.
2. **The brief must state the tool-error convention** — that
   `{'status': 'exception'}` means the tool failed despite the call being
   green — so the reviewer does not read a traceback as a success artifact.

A verifier that inherits the framework's own false-green assumption is worse
than no verifier: it manufactures false confidence at scale, in parallel.

---

## 4. Prerequisite: session name scoping

`AgentVersionModel.get_or_create_session` (`server/models/agents/agent_version.py:59+`)
resolves with `SessionModel.objects.get_or_create(name=name, defaults=...)`.
`name` is the **only** lookup key; `parent_session` sits in `defaults`, so it
applies on create only. `SessionModel.name` (`server/models/sessions/session.py:32`)
is a bare `CharField` with no unique constraint.

Consequences today:

- Two projects that each name a session `research` share **one** row — one
  `turn_count`, one message chain, one Query slot.
- `list_subsessions` filters by `parent_session`, so each parent is blind to a
  session it is in fact sharing.
- With no constraint, two concurrent creations of the same name insert
  duplicate rows.

Work-item dispatch creates one executor session per item, which is exactly the
access pattern that amplifies this.

**Change:** move `parent_session` into the lookup and add a `UniqueConstraint`
on `(name, parent_session)`.

**Open implementation detail:** top-level sessions have `parent_session = NULL`,
and Postgres treats NULLs as distinct in unique constraints. Resolve by
choosing a sentinel, a separate constraint, or a partial-index-only migration —
after inspecting live data for existing duplicates.

**Mitigation regardless:** work-item executors use `name = f"workitem:{pk}"`,
which is globally unique by construction and immune to the collision.

---

## 5. Data model

`server/models/workitems/work_item.py` — follows the `ObservableMixin` /
explicit `Observables` convention of `server/models/project.py:8-27`.

| Field | Type | Notes |
|---|---|---|
| `project` | FK → `Project` | `SET_NULL`, `null=True`, `related_name="work_items"`. Nullable so items can be triaged before filing. |
| `parent` | FK → self | `SET_NULL`, `null=True`, `related_name="child_items"`. Enables decomposition. |
| `title` | `CharField(255)` | |
| `body` | `TextField` | Dispatched as the turn prompt. |
| `status` | `WorkItemStatus` | Own FSM (§6). Never written by ATC/Run code. |
| `priority` | `int`, default `0` | Ready-queue ordering, descending. |
| `order` | `int`, default `0` | Manual ordering among siblings. |
| `assigned_agent` | FK → `AgentModel` | `SET_NULL`, `null=True`. Unassigned items are blocked, not dispatched. |
| `executor_session` | FK → `SessionModel` | `SET_NULL`, `null=True`. The session this item runs in. |
| `root_task` | FK → `AgentTaskCall` | `SET_NULL`, `null=True`. The ATC of the current/last dispatch. |
| `dispatch_count` | `int`, default `0` | Observability; also the v1.1 requeue bound (§13). |
| `requires_verification` | `bool`, default `False` | Opt-in. Not all work needs a second opinion — running a migration is self-evidencing; a research document is not. |
| `verify_status` | `CharField` | `pending` / `approved` / `rejected` / `escalated` / `skipped`. Mirrors the ATC's `auto_review_status` (`agent_task_call.py:80`). |
| `verify_reason` | `TextField` | The reviewer's stated justification. |
| `verify_attempts` | `int`, default `0` | Bounds the reject→requeue→verify cycle (§8.5). |
| `last_outcome` | `TextField` | `status_detail` plus a result summary. |
| `started_at` / `completed_at` | `DateTimeField`, null | |
| `created_at` / `updated_at` | `DateTimeField` | `auto_now_add` / `auto_now`. |

Because state lives in the database rather than being replayed from
`result_json`, a work item survives context compaction, session deletion and
full process restarts with no extra machinery.

Migration: `0131_workitem.py` (latest existing is `0130_...`).

---

## 6. State machine

`runtime/workitems/workitem_fsm.py` — mirrors `runtime/tasks/call_fsm.py`:
a `_VALID_TRANSITIONS` frozenset (`:11-81` there) plus named methods delegating
to a single atomic `transition()` guarded by `WHERE status = <from>`.

### 6.1 States

```
        ┌─────────┐
        │ backlog │
        └────┬────┘
             │ mark_ready
        ┌────▼────┐   unblock    ┌─────────┐
        │  ready  ├────────────►│ blocked │
        └────┬────┘◄────────────└────┬────┘
             │ start_dispatch        │ (human re-queue)
        ┌────▼──────────┐            │
        │  in_progress  ├────────────┘
        └───┬───────┬────┘
 report_*   │       │  report_success + requires_verification
  (failure) │       │
     ┌──────▼──┐  ┌▼─────────┐   approve
     │ blocked │  │ in_review├──────────►┌───────┐
     └─────────┘  └┬───────┬──┘            │ done  │
             reject└───────┘escalate      └───────┘
                     │        │
                     ▼        ▼
                  ┌──────────────────┐
                  │ blocked (human)  │
                  └──────────────────┘
```

Terminal states are `done` and `cancelled`; `done` may be reopened to
`in_progress`, `cancelled` may be restored to `ready`.

### 6.2 Transitions

| From | Allowed to |
|---|---|
| `backlog` | `ready`, `cancelled` |
| `ready` | `in_progress`, `blocked`, `backlog`, `cancelled` |
| `in_progress` | `in_review`, `blocked`, `done`, `ready`, `cancelled` |
| `in_review` | `done`, `blocked`, `in_progress`, `cancelled` |
| `blocked` | `ready`, `in_progress`, `cancelled` |
| `done` | `in_progress` |
| `cancelled` | `ready` |

Methods: `mark_ready`, `mark_blocked`, `start_dispatch`, `report_success`,
`report_failure`, `begin_review`, `approve`, `reject`, `escalate`, `cancel`,
`reopen`.

`mark_blocked` and `reject` take a reason recorded into `last_outcome`;
`approve` / `reject` / `escalate` also write `verify_status` and `verify_reason`.

`mark_ready` additionally clears the *previous attempt's* bookkeeping —
`root_task`, `verify_status`, `verify_reason` and `completed_at` — because both
dispatch (§7.1) and the review claim (§8.4) select on those fields being NULL.
Leaving them set would strand a re-queued item in `ready` forever: it would
never re-dispatch, and its stale verdict would block it from ever being
re-reviewed. `verify_attempts`, `dispatch_count` and `executor_session` are
deliberately *kept*, so the reject/verify budget stays cumulative (§8.5) and a
re-dispatch continues the same conversation.

### 6.3 Completion semantics

An item reaches `done` by one of two routes:

- **Verified** — `requires_verification` is set, an agent reviewer approved it
  (§8).
- **Unverified** — the flag is unset and a human moved it to `done`, or
  approval came back `ask_human` and a human confirmed.

A human always retains the final say: `done → in_progress` (reopen) and
`in_review → done` (confirm) are both legal transitions. Verification reduces
human attention, it does not remove it.

---

## 7. Dispatch pipeline

Three new routines in the isolation loop at `server/tasks/tick_scheduler.py:53-60`.
Each is wrapped in its own `try`, so a work-layer bug can never starve the
release passes.

```python
for routine in (
    _dispatch_data_flows,
    _propagate_from_collections,
    _release_scheduled_calls,
    _release_rate_limited_calls,
    _release_retry_calls,
    _release_queued_calls,
    _dispatch_work_items,        # new
    _report_work_item_outcomes,  # new
    _verify_work_items,          # new
):
```

### 7.1 `_dispatch_work_items`

1. Select `WorkItem.objects.filter(status=READY, root_task__isnull=True)`,
   ordered by `(-priority, created_at)`.
2. Per item: resolve `assigned_agent`. **If unset → `mark_blocked("no agent
   assigned")` and continue.** Never dispatch an unassigned item.
3. Ensure the executor session:
   `get_or_create_session(name=f"workitem:{pk}", session_type=SUBSESSION, ...)`.
   The session name is scoped by `parent_session` (§11), so a re-queued item
   continues its own conversation instead of colliding with another one.
4. Create the user `Message` carrying `body`, then dispatch **`process_turn`**
   (`executor.get_task("process_turn").delay(message=message)`) and record the
   returned ATC as `root_task`, along with `executor_session`, `started_at`,
   `dispatch_count += 1`, then `start_dispatch`.

   *Deviation from the original draft, which said to dispatch
   `ingest_user_message`:* that call is short-lived and its ATC is not the unit
   of work. `root_task` must be the **`process_turn`** call, because that is the
   ATC whose terminal `status`/`status_detail` decide the outcome (§7.2) and
   whose call tree carries the evidence a reviewer judges (§8). Dispatching the
   turn directly also avoids an extra queue hop in front of every item.

**Idempotency:** an item is only selected while `root_task` is NULL, and
`root_task` is set in the same pass that starts the turn, so a second tick
cannot dispatch it twice. This is what makes it safe for the 10s tick to run
the routine unconditionally.

**Requeue:** `mark_ready` clears `root_task` and `verify_status` (see §6), so
a re-queued item is selectable again instead of being stranded in `ready`.

**No age guard:** must not call `_is_ancient` (§2.3).

### 7.2 `_report_work_item_outcomes`

For each `in_progress` item whose `root_task.status == ENDED`:

| `root_task.status_detail` | Action |
|---|---|
| `ENDED_SUCCESS`, `requires_verification` | `report_success(...)` → `begin_review()`, i.e. → `in_review` |
| `ENDED_SUCCESS`, no verification | `report_success(...)` → `blocked("awaiting review")` |
| any other `ENDED_*` | `report_failure(...)` → records `status_detail`, → `blocked(reason)` |
| not `ENDED` | no-op |

### 7.3 `_verify_work_items`

Thin launcher only; the review itself runs on a worker (§8). Select
`in_review` items where `verify_status` **is null**, atomically claim each with
`filter(pk=..., verify_status__isnull=True).update(verify_status="pending")`,
and `celery_delay(WorkItemVerifier.verify, pk)` only for the rows the claim
actually won.

Claiming *before* dispatching is what makes this idempotent — a second tick sees
`pending` and leaves the in-flight review alone. It also means `pending` means
"a reviewer is already out", not "queued", so a reviewer that dies leaves the
item parked for a human instead of being retried in a loop (§8.5). A
NULL-only claim is therefore deliberate: selecting `pending` as well would make
every tick re-dispatch the same in-flight review.

`verify()` re-checks that the item is still `in_review` *and* `pending` before
doing any work, so a human decision that lands between the claim and the worker
picking it up is not overwritten.

### 7.4 Deliberate limitation

Success without verification transitions to **blocked**, never back to `ready`.
One dispatch therefore requires one human action; a subtask needing five agent
turns costs five clicks. The bounded alternative is v1.1 (§13).

Verified items do loop — reject → `blocked` → human re-queue — but that loop is
bounded by `verify_attempts` (§8.5).

---

## 8. Agent verification

An item flagged `requires_verification` is reviewed by a **separate agent**
before it can reach `done`.

### 8.1 Why reuse the auto-review shape

The approval auto-review (`runtime/tasks/call_scheduler.py:430-605`) already
solves "spawn a judge session, hand it evidence, have it call back a verdict
tool." Its properties are exactly the ones verification needs:

- **Pull model.** The reviewer calls a tool that applies the verdict; the
  framework never parses free text for a decision.
- **Never trusts a hallucinated id.** The target id is declared in the child
  session's settings (`call_scheduler.py:589-592`) and read back by the
  verdict tool (`approval_verdict.py:93-119`).
- **Fails safe.** Any exception escalates to a human rather than dropping the
  decision (`call_scheduler.py:491-496`).

`WorkItemVerifier` copies this structure. It does not add a new mechanism.

### 8.2 Flow

```
report_success ──► in_review
                     │
        _verify_work_items (tick, marks pending)
                     │
        celery_delay ─► verify(pk)          [worker]
                            │  build brief
                            ▼
              work_verifier session (fresh context)
                            │  calls workitem_verdict
                            ▼
              ┌─────────────┼─────────────┐
            approve       reject       ask_human
              │             │             │
             done         blocked       stays in_review
                     (verify_attempts++)   (human decides)
```

### 8.3 The brief

Composed by `_build_verification_brief`, mirroring `_build_review_brief`
(`call_scheduler.py:499-537`). Contents:

1. The requirement — `title` and `body`.
2. The executor's `final_result` content, if it called one.
3. The last N assistant message texts (N bounded, default 10).
4. Per-ATC summaries across the item's call tree: tool name + a truncated
   `result_json`. The tree is matched as
   `Q(session_root_task=root_task) | Q(pk=root_task_id)` — the `pk` arm is
   required, because a `process_turn` ATC created under a parent run points
   `session_root_task` at an *ancestor* call, so matching that column alone
   silently drops the dispatch call whose payload matters most.
5. The tool-error convention (§3.2), stated explicitly.
6. `status_detail` — **labelled as a routing hint that does not indicate
   success**, with the reason from §3.1.
7. The work item id, for the verdict tool to echo.

The full transcript is deliberately excluded — the reviewer has a fresh
context, and an unbounded transcript would make verification cost more than
the work itself.

### 8.4 Verdict tool

`workitem_verdict(work_item_id, decision, reason)` in
`.agentone/agents/work_verifier/scripts/`, registered as a `TaskType.TASK`
against that agent. Mirrors `approval_verdict.py:121-142`.

| `decision` | Effect |
|---|---|
| `approve` | `verify_status="approved"`, `approve()` → `done` |
| `reject` | `verify_status="rejected"`, `reject(reason)` → `blocked`, `verify_attempts += 1` |
| `ask_human` | `verify_status="escalated"`, stays `in_review` for a human |

### 8.5 Bounds — the part that must not be wrong

Three loops are possible, and each is bounded by construction:

| Loop | Bound |
|---|---|
| Auto-requeue on success (v1.1) | `dispatch_count < max_dispatches` (§13) |
| reject → re-queue → verify → reject | `verify_attempts < max_verify_attempts` (default 3). On exceeding, `escalate()` to a human instead of dispatching another reviewer. |
| Reviewer session dies | `verify_status` stays `pending`; it is never re-dispatched automatically, so the item parks for a human. |

The second bound is why `verify_attempts` is a model field rather than a local
variable — the cycle spans separate dispatches, days apart, and must survive a
restart.

### 8.6 No self-review

The reviewer is resolved by name (`work_verifier`), as `approval_decider` is
at `call_scheduler.py:577`. It **must not be the executing agent** — an agent
grading its own output is self-certification, and would make the `done` column
decorative. The `work_verifier` agent is looked up at dispatch; if it is not
loaded, the item escalates to a human rather than falling back to the
executor.

---

## 9. Agent-facing tool

`.agentone/scripts/workitems/workitem_action.py`, registered in
`scripts.md` as `TaskType.TOOL` — visible to the LLM, unlike the todo anchor
which is hidden as a `TASK`. The planner must be able to see these.

Tools: `workitem_create`, `workitem_update`, `workitem_list`,
`workitem_add_child`. All return `(bool, dict)` per the project convention.

Child items are ordinary `WorkItem` rows with `parent` set, so a subtree can be
reported on collectively.

### 9.1 What the model actually sees

**Only the function docstring reaches the LLM.** `load_python_entry` derives a
tool's description from `generate_schema_for_function(func)`, and
`_collect_manifest_entries` reads just `group`/`tools`/`tasks`/`commands` from a
manifest — the prose *below* a manifest's frontmatter, and a script's module
docstring, are developer notes and are never sent. Agent-facing guidance
therefore has to live in each function's docstring; the manifest prose and the
`agentone` agent's "Working with Work Items" section are the places a human
maintainer will actually look for it, so all three are kept in step.

Three consequences worth stating, because each one was a live bug:

- A refused write must be *reported*. The FSM signals a lost race by returning
  `False`, not by raising, so a tool that ignores the return value reports
  success for a no-op. Every branch in `_apply_status` checks it.
- The status parameter is a `Literal`, so the generated schema carries an
  `enum`. A free `str` lets a model invent `"in_progress"`, which is not
  settable by an agent.
- The requirement text has to be readable. `summarise()` is compact and
  omits `body`; `workitem_list` is the only way to read an item back, so it
  returns `summarise_with_body()` unless `include_body=False`.

### 9.2 Scoping

`_visible_items` scopes every tool to the session's project. A session with
**no** project is the unfiled inbox: it sees and creates only items that
themselves have no project. Returning the whole table for that case would mean
a session that merely lost its project association silently gained read and
write access to every project on the instance.

The UI is a separate path and deliberately differs: the board's "All projects"
is an explicit human choice to see everything plus the unfiled inbox.

---

## 10. Testing

`server/tests/test_workitem_*.py`

1. FSM — every valid transition succeeds; invalid transitions raise.
2. Dispatch creates the executor session and the ATC, with a
   collision-proof `workitem:{pk}` name.
3. **No auto-requeue loop** — a `ENDED_SUCCESS` outcome must not produce a
   second dispatch.
4. Idempotency — running the tick routine N times over one item produces
   exactly one ATC.
5. Outcome reporting — success and failure both land in `blocked` with
   `last_outcome` set.
6. **Session-name uniqueness under concurrency** — regression test for §4.
7. Parallel siblings — two `ready` items dispatch to two independent
   executor sessions.
8. Unassigned item blocks instead of dispatching.
9. Verification routing — `requires_verification` sends an `ENDED_SUCCESS`
   item to `in_review`; without the flag it goes to `blocked`.
10. Verdict tool — `approve` → `done`, `reject` → `blocked`, `ask_human` →
    stays `in_review`.
11. **Reject loop is bounded** — `verify_attempts` exceeding the cap escalates
    to a human and does not dispatch another reviewer.
12. **Reviewer failure is safe** — a `WorkItemVerifier.verify` exception leaves
    `verify_status="pending"` and never auto-approves.
13. **No self-review** — the reviewer session's agent is not the executor.
14. **False-green is not trusted** — a brief built from an executor whose only
    tool returned `{'status': 'exception'}` contains that payload and the
    convention note of §3.2, not a bare "success" signal.

Added while implementing, each covering a way the loop above could silently
strand an item (see §12a):

15. **The root call's own payload reaches the brief** when its
    `session_root_task` points at an ancestor (the production shape).
16. **A rejected item can be requeued and re-dispatched** — `root_task` and
    `verify_status` are cleared, the budget is not, and the second dispatch
    increments `dispatch_count`.
17. The tick claims an unclaimed (`verify_status IS NULL`) review exactly once.
18. `done` on an `in_progress` item completes it rather than silently blocking
    it via `report_success`.
19. `done` on an `in_review` item goes through `approve()` and stamps a verdict.
20. Created/updated items report their **post-transition** status, not the
    stale in-memory one.
21. The agent tool cannot read, update, list, or parent onto another
    project's items.
22. Blocking requires a reason; an unknown status is rejected.

---

## 11. Files

| File | Action |
|---|---|
| `server/models/workitems/work_item.py` | new |
| `server/models/workitems/enums.py` | new — `WorkItemStatus` |
| `server/models/workitems/__init__.py` | new |
| `server/migrations/0131_workitem.py` | new |
| `runtime/workitems/workitem_fsm.py` | new |
| `runtime/workitems/__init__.py` | new |
| `runtime/workitems/work_item_verifier.py` | new — `WorkItemVerifier.verify`, `_build_verification_brief` |
| `server/tasks/tick_scheduler.py` | three routines + registration |
| `.agentone/agents/work_verifier/agent.md` | new — reviewer agent |
| `.agentone/agents/work_verifier/scripts/workitem_verdict.py` | new |
| `.agentone/agents/work_verifier/scripts/scripts.md` | new |
| `.agentone/scripts/workitems/workitem_action.py` | new |
| `.agentone/scripts/workitems/scripts.md` | new |
| `server/migrations/0132_session_name_unique.py` | new — per-parent session-name constraint |
| `server/models/sessions/session.py` | unique constraint |
| `server/models/agents/agent_version.py` | scoped lookup |
| `server/tests/test_workitem.py` | new — 42 tests |
| `.agentone/agents/agentone/agent.md` | add `workitems.*` so the planner can see the tools (§9) |
| `AGENTS.md` | directory-ownership row, tick-split note, correct the recovery-beat claim at `:84` |
| `docs/user-guide.md:32` | remove the Kanban claim while the button is hidden |

---

## 12. Open questions

### 12a. Deviations from the original draft

Found while implementing; each is a deliberate change, recorded so the next
reader does not "fix" it back.

1. **`process_turn`, not `ingest_user_message`, is `root_task`** (§7.1).
2. **The review claim is NULL-only** — `pending` means in-flight, not queued
   (§7.3).
3. **`mark_ready` clears `root_task`/`verify_status`** (§6). Without this a
   re-queued item can never re-dispatch or be re-reviewed.
4. **The brief matches the root ATC by `pk` as well as `session_root_task`**
   (§8.3) — otherwise the dispatch call's own payload is dropped.
5. **Top-level session names are not DB-unique** (open question 3 below). The
   migration's constraint covers rows with a non-NULL `parent_session`; MariaDB
   treats NULLs as distinct in a `UNIQUE` index, so the lookup is scoped in
   application code instead.

### 12b. Still open

1. **Dispatch ergonomics** — is one-dispatch-per-human-action (§7.4)
   acceptable for increment 1, or is bounded auto-requeue required now?
2. **Project requirement** — `project` is drafted nullable for inbox triage.
   Confirm, or make it required.
3. **Session constraint shape** — how to constrain top-level sessions whose
   `parent_session` is `NULL` (§4).
4. **Orphaned CSS** — retain `ui/static/css/main.css:3669-3938` for a possible
   board, or delete it? It implies a multi-user design that a single-user
   scope may not want.
5. **Verification default** — `requires_verification` defaults to `False`. For
   a single user running many parallel agents, an opt-out default (verify
   unless told otherwise) may be the safer posture. Confirm.
6. **Reviewer model** — should `work_verifier` run on a stronger/larger model
   than the executors? Judging work is often harder than doing it, and a
   weaker reviewer will rubber-stamp.
7. **`max_verify_attempts` default** — drafted as 3 (§8.5). Lower means faster
   human escalation; higher means more agent autonomy.

---

## 13. Future work

**v1.1** — bounded auto-requeue. On `ENDED_SUCCESS`, requeue while
`dispatch_count < max_dispatches`; otherwise block. Reuses the existing field.

**v1.2** — board UI. A read-only list view is cheap once the model exists and
validates the concept before investing in drag-and-drop.

**v1.3** — todo list migration. Project the existing per-session todos onto a
`WorkItem`'s children, replacing the `result_json` event sourcing.

**v2** — structured result schema. Verification currently judges free text
against the requirement. A declared `WorkItem.result_schema` would let the
verifier check the deliverable mechanically before judging quality, and would
give the reserved `ENDED_FAILURE_LOGIC` state
(`server/models/enums/task_enums.py:66`) a real writer for goal-level rejection,
distinct from tool-level error reporting (§3.1).
