# Task State Machines

Formal specification of the `AgentTaskCall` and `AgentTaskRun` state machines — transition matrices, paired lifecycle, invariants, error paths, and gap analysis.

## Files

| File | Content |
|---|---|
| `01-atc-states.md` | ATC states, 32-entry transition matrix, all named methods |
| `02-run-states.md` | Run states, 8 valid transitions (9 matrix rows inc. rollback), all named methods, `RATE_LIMITED` now FSM-based |
| `03-paired-transitions.md` | ATC↔Run paired lifecycle, race conditions, sequence diagrams |
| `04-invariants.md` | 8 invariants with SQL queries |
| `05-error-recovery.md` | 11 error paths (E1-E11) including hard kill, crash, restart, deadlock |
| `06-gap-analysis.md` | 2 gaps (G1-G2) found in the current implementation |
| `07-reference.md` | Key code references with file paths and line numbers |

## Concepts

- **AgentTaskCall (ATC)** — a single invocation of a task definition. Analogous to a promise/future. Has coarse status (`NEW→WAITING→ACTIVE→HALTED→ENDED`) and detailed status (`status_detail`, ~15 values).
- **AgentTaskRun (Run)** — a single execution attempt of an ATC. An ATC may have multiple runs (retries). Statuses: `NEW→QUEUED→ACTIVE→SUCCESS/FAILURE/WAITING_RESULTTASKS`.
- **CHAIN execution** — `process_turn` is a CHAIN task. Its `apply()` iterates child instances, calling `apply_async()` on each. Each child becomes a **result reference**; the run enters `WAITING_RESULTTASKS` and waits for all children to end.
- **Paired transitions** — ATC and Run are updated together at key points (start, complete, fail). Race conditions are handled via atomic `WHERE status=X` updates.

## Key Source Files

| File | Role |
|---|---|
| `server/models/tasks/agent_task_call.py` | ATC model |
| `server/models/tasks/agent_task_run.py` | Run model + `apply()` execution |
| `runtime/tasks/call_fsm.py` | ATC state machine |
| `runtime/tasks/run_fsm.py` | Run state machine |
| `runtime/tasks/call_scheduler.py` | ATC lifecycle orchestration |
| `runtime/tasks/run_scheduler.py` | Run lifecycle orchestration |
| `server/tasks/tick_scheduler.py` | 10s tick: dispatch, propagate, release scheduled/rate-limited/retry calls, cron |
| `server/tasks/recovery_scheduler.py` | 60s recovery pass (`tasks.tick_scheduler_recovery`) + one-time `tasks.startup_cleanup` |
