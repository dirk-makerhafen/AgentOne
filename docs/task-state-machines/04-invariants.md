# Invariants

These must always hold, including mid-transition and after crash/restart. Each invariant includes a SQL query to verify.

## I1: At most one non-ended run per ATC

```sql
SELECT agent_task_call_id, COUNT(*) as cnt
FROM server_agenttaskrun
WHERE status NOT IN ('SUCCESS', 'FAILURE')
GROUP BY agent_task_call_id
HAVING cnt > 1;
```

**Rationale:** `start_new_taskrun` creates a run only when ATC transitions `WAITING_QUEUE → ACTIVE_QUEUED`. Retries create a new run only after the previous one reached `FAILURE`. The paired transition in `RunScheduler._apply_async` prevents concurrent executions.

**Enforcement:** `pick_up()` (`call_fsm.py:251`) uses atomic `WHERE status_detail=WAITING_QUEUE`, so only one call transitions. `start_new_taskrun` also enforces the per-task-instance parallel limit, which indirectly limits runs per ATC since each ATC is in one task instance.

**Admission control:** `start_new_taskrun` (call_scheduler.py:210-266) serializes dispatch for a task_instance on its row via `select_for_update()` when `limit_per_instance_parallel_runs > 0`. The count-check, `pick_up()`, and run creation run inside one transaction, so two concurrent dispatches for different ATCs on the same `task_instance` cannot both pass the count check (I1 race — fixed).

## I2: An ENDED ATC has no non-ended runs

```sql
SELECT ac.id, ac.status_detail
FROM server_agenttaskcall ac
JOIN server_agenttaskrun ar ON ar.agent_task_call_id = ac.id
WHERE ac.status = 'ENDED'
  AND ar.status NOT IN ('SUCCESS', 'FAILURE');
```

**Rationale:** Once an ATC is ENDED, no new runs can be created (transition to `ACTIVE_QUEUED` is blocked). All existing runs should be terminal.

**Enforcement:** If the ATC is externally cancelled (`ENDED_CANCELLED`) while a run is still `ACTIVE` (worker hasn't finished `apply()`), `_on_taskcall_ended` (call_scheduler.py:391-403) sweeps all non-terminal runs to `FAILURE` at force-end time (see I4). The `start_running()` guard additionally blocks new runs from spawning after cancellation.

**`start_running()` guard:** When a child ATC is about to transition `ACTIVE_QUEUED → ACTIVE_RUNNING` and start a run, `call_fsm.start_running()` (`call_fsm.py:269-296`) rejects activation if the call's `session_root_task` (the root of its turn) is already `ENDED`. The `extra_filter` on the atomic transition checks `session_root_task__status` is not ENDED (and allows NULL for the root-race window). This prevents a cancelled turn from spawning new runs after cancellation — the child's run rolls back to `QUEUED` instead.

## I3: ACTIVE_RUNNING ATC has exactly one ACTIVE run

```sql
SELECT ac.id, COUNT(*) as cnt
FROM server_agenttaskcall ac
JOIN server_agenttaskrun ar ON ar.agent_task_call_id = ac.id AND ar.status = 'ACTIVE'
WHERE ac.status_detail = 'ACTIVE_RUNNING'
GROUP BY ac.id
HAVING cnt != 1;
```

**Rationale:** The paired transition in `RunScheduler._apply_async` (run `QUEUED → ACTIVE`, ATC `ACTIVE_QUEUED → ACTIVE_RUNNING`) is designed to be atomic. If it succeeds, the ATC is ACTIVE_RUNNING with one ACTIVE run.

## I4: Non-ACTIVE_RUNNING ATC has zero ACTIVE runs

All states except `ACTIVE_RUNNING` should have no `ACTIVE` runs. Transition out of `ACTIVE_RUNNING` happens after `apply()` returns, which also sets the run to a terminal state.

**Enforcement:** Force-end paths (`_force_end_call` in `recovery_scheduler.py`, `_cancel_safe` in `call_scheduler.py`) can end an `ACTIVE_RUNNING` call while its worker is still mid-`apply()`. `CallScheduler._on_taskcall_ended()` (call_scheduler.py:391-403) sweeps all non-terminal runs of the ending call to `FAILURE` (with `ended_at`). Every force-end path funnels through `_on_taskcall_ended`; normal completion paths are no-ops because the run is already `SUCCESS`/`FAILURE`. Race-safe against the in-flight worker: its later `succeed()`/`fail()` uses atomic `WHERE status=ACTIVE|WAITING_RESULTTASKS`, which no-ops on the already-FAILED run. Mirrors the run sweep in `_recover_stuck_calls` step 3.

## I5: ENDED_SUCCESS ATC has a `taskcall_result_run`

```sql
SELECT id FROM server_agenttaskcall
WHERE status_detail = 'ENDED_SUCCESS' AND taskcall_result_run_id IS NULL;
```

**Rationale:** `succeed()` always sets `taskcall_result_run_id`. If the query returns rows, a code path reached `ENDED_SUCCESS` without going through `succeed()`.

## I6: WAITING_SUBTASKS_OR_HOOKS ATC has a `taskcall_result_run`

```sql
SELECT id FROM server_agenttaskcall
WHERE status_detail = 'WAITING_SUBTASKS_OR_HOOKS' AND taskcall_result_run_id IS NULL;
```

Same rationale as I5. `wait_for_hooks()` always sets `taskcall_result_run_id`.

## I7: Message chain has no forks

```sql
SELECT session_version_id, COUNT(*) as tail_count
FROM server_message
WHERE id NOT IN (
    SELECT prev_message_id FROM server_message WHERE prev_message_id IS NOT NULL
)
GROUP BY session_version_id
HAVING tail_count > 1;
```

For each session, the `prev_message` chain forms a single linked list from root to tail. `filter(next_messages=None)` must return exactly one message (the true tail).

**Rationale:** `ingest_user_message` and `ingest_assistant_message` use `filter(next_messages=None).last()` to find the predecessor. If this returns multiple messages, message ordering is undefined and context building may behave incorrectly.

**Enforcement:** `ingest_compaction` (`.agentone/scripts/core/ingest_compaction.py`) repoints the kept message at the new compaction message, detaches the compacted range from its predecessor, then self-references every message no longer reachable from the compaction message (backward via `prev_message`, forward via `next_messages`). This keeps the linked list a single chain. Regression coverage: `server/tests/test_compact_fork.py`.

**Historic violation:** A historic compaction bug caused chain forks (see `.agentone/scripts/core/repair_message_chain.py`). The repair script self-references orphan messages so they are excluded from `filter(next_messages=None)`. The bug is fixed in the current `ingest_compaction`; the repair script remains for pre-existing corrupted sessions.

## I8: Self-referencing prev_message excludes from filter(next_messages=None)

When `msg.prev_message = msg.id`, the message appears in its own `next_messages` queryset via the reverse FK `related_name="next_messages"`. Since `next_messages` is not null, `filter(next_messages=None)` correctly excludes it.

This is used by the repair script (`repair_message_chain.py`) and by `ingest_compaction` to hide orphan messages from the tail query without deleting them.

**Note:** The FK has `on_delete=SET_NULL`, so if a self-referencing message is deleted, its `prev_message` goes to NULL and it would reappear in `filter(next_messages=None)`. In practice, messages are not deleted.
