# Error and Recovery Paths

## E1: Celery Worker Crashes Mid-Execution

**Scenario:** Worker process is killed (SIGKILL, OOM, machine failure) while `apply()` is running.

**DB impact:**
- TaskRun remains in `ACTIVE` (transition to SUCCESS/FAILURE never fired)
- ATC remains in `ACTIVE_RUNNING`

**Recovery** (`recovery_scheduler._recover_stuck_calls` step 3, line 250):
```
For each ACTIVE_RUNNING ATC with updated_at > 15min ago:
  If no ACTIVE run exists:
    - Fail all non-ended runs (QUEUED, WAITING_RESULTTASKS, RATE_LIMITED)
    - If retries remain → WAITING_RETRY
    - Else → ENDED_FAILURE_EXCEPTION
```

**Race:** If worker is still alive but the tick fires first (possible if the worker is slow but not dead), the run is incorrectly failed. Mitigated by 15-minute timeout.

**Code:** `recovery_scheduler.py:250-276`

## E2: Celery Beat Crashes (Tick Never Fires)

**Scenario:** Beat process dies. No recovery ticks for minutes or hours.

**Impact:** All time-driven activities halt:
- `WAITING_RATELIMIT` calls never released
- `WAITING_RETRY` calls never released
- `WAITING_QUEUE` fallback drain never runs
- Active run timeouts never detected
- Stuck `WAITING_RESULTTASKS` runs never recovered

**Net effect:** All pipeline activity stops. Runs that complete on workers finish, but the next chain step is never dispatched. On beat restart, the 10s tick resumes immediately and the 60s recovery pass catches up within a minute.

**No data loss:** Since all state is in the database, no messages or state is lost. Work resumes when beat restarts.

## E3: Celery Message Loss (Apply_Async Never Reaches Worker)

**Scenario:** `apply_async()` sends a Celery message that is lost (Redis flush, broker crash, network partition).

**DB impact:**
- ATC in `ACTIVE_QUEUED` (pick_up succeeded)
- TaskRun in `QUEUED` (never picked up by worker)

**Recovery** (`recovery_scheduler._recover_stuck_calls` steps 1-2):
```
Step 1: ACTIVE_QUEUED → if root task already ENDED, cancel (can never start;
        start_running guard rejects it).  Else if no runs → re_queue() + re-dispatch
Step 2: QUEUED runs with updated_at > 15min → re-dispatch Celery message
```

**Code:** `recovery_scheduler.py:206-248`

## E4: Hard Kill — Entire Process Tree Dies

**Scenario:** User kills the terminal (SIGKILL), or `systemctl stop`, or catastrophic machine failure. Daphne + Celery worker + Beat all die simultaneously.

**DB impact:** Combination of E1, E2, E3. Runs in ACTIVE are orphaned. QUEUED messages lost. Scheduled recovery never fires until beat restarts.

**Recovery sequence on restart:**
1. `server run` dispatches `startup_cleanup` (one-time): cleans stale runtime folders **and immediately runs the release/recover passes** (`_release_queued_calls`, `_recover_stuck_calls`, `_recover_stale_queries`) so orphaned state is handled at t+0s instead of waiting for the 60s beat
2. Beat starts → 10s tick at t+10s: `_release_scheduled_calls`, `_release_rate_limited_calls`, `_release_retry_calls` release what's due
3. 60s recovery pass (`tasks.tick_scheduler_recovery`) fires at t+60s:
   - `_release_queued_calls`: drains WAITING_QUEUE backlog (cancels calls with dangling arg references)
   - `_timeout_active_runs`: fails runs past their time limit
   - `_resolve_stuck_waiting_runs`: handles WAITING_RESULTTASKS runs (deadlock breaking)
   - `_recover_stuck_calls`: handles all 6 orphan cases
   - `_cancel_duplicate_queries` / `_recover_stale_queries`: query-level recovery

**Critical observations:**
- Recovery now runs on its own 60s beat entry — no longer gated behind `random.randint(0,10) == 5` on the 10s tick. After a full restart, recovery fires deterministically at t+60s.
- The 15-minute timeout on ACTIVE recovery means runs that were genuinely in progress survive as long as they finish within 15 minutes.
- New `ingest_user_message` calls proceed normally after restart (they follow the `NEW → WAITING_DEPENDENCY → WAITING_QUEUE` path and get picked up by the worker).

## E5: Circular Deadlock — WAITING_RESULTTASKS Loop

**Scenario:** `decide_next_step` detects tool calls and dispatches `process_turn.delay()`. The old `process_turn` run is in `WAITING_RESULTTASKS` waiting for `decide_next_step`'s result. The new `process_turn` can't start because `limit_per_instance_parallel_runs=1` blocks it.

```
decide_next_step (WAITING_RESULTTASKS)
  → waiting for new process_turn
    → blocked by old process_turn (ACTIVE_RUNNING/holding limiter)
      → old process_turn waiting for decide_next_step
```

**Prevention (root cause):** The new `process_turn` is a *same-turn continuation* — it is a descendant of the old `process_turn`'s run (spawned by `decide_next_step`, the tail of the old chain). The per-TaskInstance limiter in `CallScheduler.start_new_taskrun` counts only runs whose calls are **not** ancestors of the call being admitted (`_ancestor_call_ids`). The continuation therefore does not count against its own ancestor's slot and is admitted, breaking the cycle at the source instead of via recovery. Genuinely independent calls (a second user message, a sibling turn) are still serialized by the limit.

**Regression:** commit `0182d96` began enforcing the previously-inert per-TI limiter; it counted *every* active run on the task_instance, so the loop continuation deadlocked against the very run that spawned it. Fixed by the ancestor exclusion. Tests: `TestParallelRunLimit.test_continuation_descendant_not_blocked_by_ancestor` / `test_unrelated_sibling_still_blocked_when_limit_reached`.

**Recovery fallback** (`recovery_scheduler._resolve_stuck_waiting_runs` case 2, line 134):
```
For each WAITING_RESULTTASKS run:
  If none of the pending refs are in ACTIVE_QUEUED or ACTIVE_RUNNING:
    If the entire root task tree has ANY progressing call (ACTIVE_QUEUED
      or ACTIVE_RUNNING) → SKIP the run.  The chain is alive but slow
      (e.g. a long call_llm several dependency levels down) — its refs
      will resolve when that call ends.  Failing here would kill a
      healthy pipeline.
    Else if the whole tree has NO progressing calls (multi-level deadlock,
      e.g. A→B→C→A) → fail immediately, skip the 30s grace
    Else wait 30s grace period (since updated_at)
    Fail the run → breaks the cycle
  Max 5 per pass (line 174: return), to pace the cascade
```

**Multi-level deadlock detection:** Before applying the 30s grace, the scheduler queries all non-ended calls under the same `session_root_task`. If none are `ACTIVE_QUEUED` or `ACTIVE_RUNNING`, the entire root tree is stuck — the grace period is skipped and the run fails immediately. This catches cycles that span more than one level (A→B→C→A) in a single tick instead of repeatedly failing runs one level at a time. Conversely, if the tree *does* contain a progressing call, the run is left alone: it is not deadlocked, only slow (see E5a).

## E5a: False-Positive Deadlock — Slow But Healthy Chain

**Scenario:** A chain whose dependency tree contains an `ACTIVE_RUNNING` call that legitimately takes longer than the 30s grace (e.g. `call_llm` taking 60s+). The direct pending refs are in `WAITING_DEPENDENCY` (not `ACTIVE_QUEUED`/`ACTIVE_RUNNING`), so Case 2 fires — but the tree is making progress.

```
process_turn (WAITING_RESULTTASKS) run waiting on decide_next_step
  → decide_next_step (WAITING_DEPENDENCY) waiting on compact_if_needed
    → compact_if_needed (WAITING_DEPENDENCY) waiting on ingest_assistant
      → ... → call_llm (ACTIVE_RUNNING)   ← genuinely progressing
```

**Recovery fix:** When the root-tree scan finds any genuinely progressing call, the run is skipped (`continue`) instead of being failed after the 30s grace. The chain is healthy-but-slow; failing the parent would cascade cancellation down the whole subtree and orphan its in-flight work.

**Progressing vs. blocked:** A call counts as *progressing* if it is either:

- `ACTIVE_QUEUED`/`ACTIVE_RUNNING`/`HALTED_APPROVAL` **and** has no run in `WAITING_RESULTTASKS` (`.exclude(related_agent_task_runs__status=WAITING_RESULTTASKS)`). A call whose own run is `WAITING_RESULTTASKS` is itself blocked, not doing work — this is exactly the E5 cycle (old `process_turn` `ACTIVE_RUNNING` while its run waits on `decide_next_step`). Without this exclusion the deadlock-breaker would see the E5 cycle as "progressing" and never break it.
- `WAITING_DEPENDENCY` **with at least one argument reference whose ALL references have ended**. Ending a dependency fires `on_arg_reference_task_ended` via Celery, so such a call is about to move to `WAITING_QUEUE`/`HALTED_APPROVAL` on its own — e.g. a CHAIN step waiting on the just-finished previous step. A `WAITING_DEPENDENCY` call with *no* argument references is NOT progressing: nothing will ever notify it, only the recovery pass can unstick it (this is what makes `test_run_with_dead_tree_is_failed` still fail).

`HALTED_APPROVAL` also counts as *progressing*: a call halted for human approval is paused on a decision, not deadlocked — the user will approve (→ `WAITING_QUEUE`) or deny (→ `ENDED_CANCELLED`), and either outcome resolves the chain. Both the per-run Case 2 `active_states` set and the tree-wide `has_progressing` query include it.

**Regression tests:** `api/tests/test_tasks.py::TestResolveStuckWaitingRuns` — `test_run_with_live_tree_not_failed` (healthy `ACTIVE` sibling protects the tree), `test_run_with_halted_approval_ref_is_not_failed` (HALTED_APPROVAL ref is not a deadlock), `test_run_with_parked_ref_and_ready_dependency_not_failed` (session-963: parked `WAITING_SUBTASKS_OR_HOOKS` ref + a `WAITING_DEPENDENCY` step whose deps have ended must *not* be force-failed), `test_run_with_dead_tree_is_failed` (no live calls), and `test_run_with_blocked_active_sibling_is_failed` (E5 cycle: an `ACTIVE_RUNNING` sibling whose run is `WAITING_RESULTTASKS` does *not* protect the tree).

**Remaining gap:** For a single-level stall where *some* sibling tree is still progressing, the fixed 30s grace still has no maximum retry count or exponential backoff. A genuinely stuck run is failed and re-failed across ticks, though each failure now resolves faster thanks to the tree-wide check.

**Code:** `recovery_scheduler.py:104-191`

## E6: Rate Limit Deadlock — All Model Slots Full

**Scenario:** All LLM models at capacity. RAPIDLY created ATCs hit `ACTIVE_RUNNING → WAITING_RATELIMIT`.

**Recovery** (`tick_scheduler._release_rate_limited_calls`):
- Every tick, iterate `WAITING_RATELIMIT` calls in FIFO order (by `priority`, `created_at`)
- For each model with capacity, release one call via `release_rate_limit()` → `WAITING_QUEUE` → `start_new_taskrun()`
- Tracks `exhausted_models` set per tick to avoid re-checking the same model

**Code:** `tick_scheduler.py:49-88`

**Per-turn release priority:** Recovery step 6 (`recovery_scheduler._recover_stuck_calls`, line 331) releases WAITING_QUEUE calls per session but prefers the newest root task. For each session, it finds the most recent root call (`session_root_task=F("pk")`) that still has WAITING_QUEUE children and releases its oldest child first. This prevents an old zombie turn's backlog from blocking fresh user requests from the same session. Falls back to session-wide FIFO if no root qualifies.

**Code:** `recovery_scheduler.py:331-358`

## E7: Duplicate Query from Race Condition

**Scenario:** User sends a message while a previous LLM call is still running. Two `call_llm` ATCs exist for the same session.

**Recovery** (`recovery_scheduler._cancel_duplicate_queries`):
1. Groups WAITING/ACTIVE queries by `session_version_id` → keeps newest, cancels rest
2. Groups WAITING/ACTIVE queries by `session_id` (across versions) → keeps newest
3. For each cancelled query, finds and force-ends its `call_llm` ATC via `_force_end_call()`

**Code:** `recovery_scheduler.py:453-549`

## E8: Stale Query from Crash

**Scenario:** A `Query` model is stuck in `ACTIVE` or `WAITING` after a crash. `build_llm_context` refuses to create a new query while one is already active.

**Recovery** (`recovery_scheduler._recover_stale_queries`):
- **WAITING queries** with no live `call_llm` → mark SUCCESS (unblocks future queries)
- **ACTIVE queries** past 15-minute timeout:
  1. Fail orphaned ACTIVE responses
  2. Find and fail `call_llm` ATCs referencing this specific query
  3. Reset query to WAITING
  4. Re-dispatch `call_llm` preserving guardrail state

**Code:** `recovery_scheduler.py:551-696`

## E9: After-Run Hook Failure Cascade

**Scenario:** An after-run hook ATC fails. The parent ATC is in `WAITING_SUBTASKS_OR_HOOKS`. The hook failure should cancel/stop the parent.

**Path** (`call_scheduler.on_posthook_ended`, line 316):
- Hook status `ENDED_STOPPED` → `stop()` parent → `ENDED_STOPPED`
- Hook status not `ENDED_SUCCESS` → `cancel()` parent → `ENDED_CANCELLED`
- Fallback: `_cancel_safe()` if parent progressed past `WAITING_SUBTASKS_OR_HOOKS`

**Risk:** If `_cancel_safe` fails to transition the parent (e.g., parent already ENDED), the notification is silently lost. The parent's dependents are never notified. The fallback now raises `RuntimeError` after the update to flag unhandled states as programming bugs (all non-terminal states have FSM paths).

**Code:** `call_scheduler.py:316-356`

## E10: Dependency (Arg Ref) Task Fails Mid-Chain

**Scenario:** In a CHAIN, one of the argument-reference ATCs fails. All dependent ATCs waiting in `WAITING_DEPENDENCY` must be cancelled.

**Path** (`call_scheduler._on_taskcall_ended`, line 404):
```
dependent_ids = AgentTaskCall.objects.filter(
    taskcall_arg_references__pk=task_call_id,
    status_detail=WAITING_DEPENDENCY,
)
for each: celery_delay(on_arg_reference_task_ended, ...)
```

**Recovery:** If Celery message is lost, `recovery_scheduler._recover_stuck_calls` step 5 (line 302) re-checks WAITING_DEPENDENCY calls against their arg refs on every recovery pass.

**Code:** `call_scheduler.py:404-414`, `recovery_scheduler.py:302-329`

## E11: Cross-Session Subagent Result

**Scenario:** A subagent session completes. `ingest_subagent_result.py` creates a user message in the parent session and (if `subagentResultDelivery == "immediate"`) dispatches `process_turn` on the parent.

**Path:**
1. Child session completes
2. `ingest_subagent_result` creates a user message in the parent
3. If immediate: dispatches `process_turn` on parent
4. `process_turn` chain runs; `decide_next_step` detects `_is_subtask_execution()` and dispatches another `process_turn` on the parent

**Risk:** The child run (on the parent) is in `WAITING_RESULTTASKS` waiting for the subagent's result. If `process_turn` creates new ATCs, they compete with the child's WAITING_RESULTTASKS resolution. The `limit_per_instance_parallel_runs=1` prevents concurrent `process_turn` instances for the same task instance, so the new `process_turn` stays in `WAITING_QUEUE` until the old one finishes. The continuation is a descendant of the old run and is admitted by the limiter's ancestor exclusion (see E5), so this resolves normally.

**Code:** `.agentone/scripts/subagents/ingest_subagent_result.py`
