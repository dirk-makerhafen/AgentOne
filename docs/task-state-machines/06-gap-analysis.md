# Gap Analysis


## G1: _resolve_stuck_waiting_runs No Backoff on Single-Level Stalls

**Code:** `recovery_scheduler.py:134-175`

**Partial fix (multi-level deadlock):** Before the 30s grace, the scheduler now queries all non-ended calls under the run's `session_root_task`. If none are `ACTIVE_QUEUED`/`ACTIVE_RUNNING`, the entire tree is deadlocked — the run fails immediately, skipping the grace (line 234-246). This resolves multi-level cycles (A→B→C→A) in one tick.

**Remaining issues (single-level case):**
- If *some* sibling tree is still progressing, the 30s grace still applies with no exponential backoff
- No maximum retry count — a genuinely stuck cycle fails, the ATC retries, the new run gets stuck again, fails again, ad infinitum
- `return` at line 174 means only 5 stuck runs are resolved per pass (even if multiple are stuck)

**Recommendation:** Track fail count per session or per ATC; after 3 consecutive fails, fail the ATC permanently instead of retrying.

## G2: _release_queued_calls Races with _on_taskcall_ended Drain

Three code paths can drain the WAITING_QUEUE simultaneously:
1. `_on_taskcall_ended` per-TI drain (`call_scheduler.py:486-494`) — fires when any ATC ends
2. `_release_queued_calls` recovery (`recovery_scheduler.py:45-61`) — every 60s pass, iterates ALL WAITING_QUEUE calls
3. `_recover_stuck_calls` step 6 (`recovery_scheduler.py:300-326`) — one per session, prefers the newest root task

All three call `start_new_taskrun`, which serializes per task_instance via `select_for_update()` on the TI row, so they can't create duplicate runs. But the ordering is non-deterministic — which ATC gets picked next depends on timing, not on queue order. The step 6 per-turn priority (releasing the newest root's oldest child first) makes the ordering deterministic per session, which reduces but doesn't eliminate the cross-path race with `_on_taskcall_ended` drain.

**Impact:** Under heavy load, FIFO ordering of ATCs within the same task_instance may be violated briefly. No data corruption risk.
