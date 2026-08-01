# AgentTaskRun — States and Transitions

**Source:** `runtime/tasks/run_fsm.py`, `server/models/tasks/agent_task_run.py:214-218`

## All Statuses

| Status | Meaning | Set via |
|---|---|---|
| `NEW` | Freshly created | FSM |
| `QUEUED` | Celery message sent, waiting for worker | FSM |
| `ACTIVE` | Worker has started execution | FSM |
| `WAITING_RESULTTASKS` | Run's result contains ATC refs; waiting for all to end | FSM |
| `RATE_LIMITED` | Run was terminated due to LLM rate limit | **Raw `.update()`** (bypasses FSM) |
| `SUCCESS` | Completed successfully | FSM |
| `FAILURE` | Failed (exception, timeout, dependency failure) | FSM |

## Transition Matrix

As defined in `_VALID_TRANSITIONS` (`run_fsm.py:9-18`):

| # | From | To | Event | Code Path |
|---|---|---|---|---|
| R1 | `NEW` | `QUEUED` | `apply_async()` called | `run_fsm.enqueue()` |
| R2 | `QUEUED` | `ACTIVE` | Worker picks up the run | `run_fsm.start()` |
| R3 | `ACTIVE` | `QUEUED` | Rollback — paired ATC transition failed | `run_fsm.rollback_to_queued()` (NOT in `_VALID_TRANSITIONS`) |
| R4 | `ACTIVE` | `SUCCESS` | Run completed, no result refs | `run_fsm.succeed()` |
| R5 | `ACTIVE` | `FAILURE` | Run raised exception | `run_fsm.fail()` |
| R6 | `ACTIVE` | `WAITING_RESULTTASKS` | Run produced result refs | `run_fsm.wait_for_results()` |
| R7 | `WAITING_RESULTTASKS` | `SUCCESS` | All result refs ended successfully | `run_fsm.succeed()` |
| R8 | `WAITING_RESULTTASKS` | `FAILURE` | A result ref failed | `run_fsm.fail()` |
| R9 | `ACTIVE` | `RATE_LIMITED` | `RateLimitError` caught in `apply()` | `run_fsm.rate_limit()` |

## Named Transition Methods

### `enqueue(run_id)` (line 104)
`NEW → QUEUED`. Called from `AgentTaskRun.apply_async()`.

### `start(run_id)` (line 109)
`QUEUED → ACTIVE`. Called from `RunScheduler._apply_async()`. If paired `start_running()` on the ATC fails, caller must `rollback_to_queued()`.

### `rollback_to_queued(run_id)` (line 120)
`ACTIVE → QUEUED`. Deliberately NOT in `_VALID_TRANSITIONS`. Only used in the rollback path when the paired ATC `ACTIVE_QUEUED → ACTIVE_RUNNING` update fails.

### `wait_for_results(run_id, extra)` (line 139)
`ACTIVE → WAITING_RESULTTASKS`. The run's result list contains AgentTaskCall references. Stays open until all reach `ENDED`.

### `succeed(run_id, extra)` (line 157)
Dual-path:
1. Try `WAITING_RESULTTASKS → SUCCESS` (all refs just finished)
2. Fallback: `ACTIVE → SUCCESS` (no result refs)

Always sets `ended_at=now()` on fallback.

### `fail(run_id, extra)` (line 180)
Dual-path:
1. Try `WAITING_RESULTTASKS → FAILURE` (a referenced call failed)
2. Fallback: `ACTIVE → FAILURE` (exception in `apply()`)

Always sets `ended_at=now()` on fallback.

## RATE_LIMITED (was bypass, now FSM-based)

Previously the `RATE_LIMITED` status was set via a raw `.update()`, bypassing the FSM. Now it uses `TaskRunStateMachine.rate_limit()` (`run_fsm.py:210-224`), which validates the transition and sets `ended_at`.

```python
except RateLimitError:
    self.status = TaskRunStatus.RATE_LIMITED
    from runtime.tasks.run_fsm import TaskRunStateMachine
    TaskRunStateMachine.rate_limit(self.pk)
```

After this, `RunScheduler._apply_async()` transitions the ATC to `WAITING_RATELIMIT` so the scheduler re-dispatches when LLM capacity returns.
