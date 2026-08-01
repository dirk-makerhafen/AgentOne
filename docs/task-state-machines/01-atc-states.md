# AgentTaskCall — States and Transitions

**Source:** `runtime/tasks/call_fsm.py`

## Coarse Status

```
NEW → WAITING → ACTIVE → HALTED → ENDED
```

## Detailed Status — All Values

| Detail | Coarse | Meaning |
|---|---|---|
| `NEW` | NEW | Freshly created, not yet processed |
| `WAITING_DEPENDENCY` | WAITING | Waiting for argument-reference ATCs to finish |
| `WAITING_RETRY` | WAITING | Delayed before retry (`dont_start_before` in the future) |
| `WAITING_QUEUE` | WAITING | Queued for execution, awaiting scheduler |
| `WAITING_SUBTASKS_OR_HOOKS` | WAITING | Run succeeded but after-run hooks still executing; also used for CHAIN waiting for sub-calls |
| `WAITING_RATELIMIT` | WAITING | Run hit LLM rate limit; waiting for capacity |
| `ACTIVE_QUEUED` | ACTIVE | Scheduler picked it up, about to create a TaskRun |
| `ACTIVE_RUNNING` | ACTIVE | TaskRun is actively executing |
| `HALTED_APPROVAL` | HALTED | Waiting for human approval |
| `HALTED_INPUT` | HALTED | Waiting for user input |
| `HALTED_STAGNATED` | HALTED | Step limit reached |
| `HALTED_PAUSED` | HALTED | Paused by user |
| `ENDED_SUCCESS` | ENDED | Completed successfully |
| `ENDED_FAILURE_EXCEPTION` | ENDED | Technical failure |
| `ENDED_FAILURE_LOGIC` | ENDED | Logic/quality failure |
| `ENDED_CANCELLED` | ENDED | Cancelled before launch |
| `ENDED_STOPPED` | ENDED | Stopped after launch |

## Transition Matrix

Each row: `from_detail → to_detail` as defined in `_VALID_TRANSITIONS` (`call_fsm.py:11-81`).

| # | From | To | Event | Trigger |
|---|---|---|---|---|
| 1 | `NEW` | `WAITING_DEPENDENCY` | `apply_async()` dispatched | `call_fsm.enter_dependency_wait()` |
| 2 | `WAITING_RETRY` | `WAITING_DEPENDENCY` | Retry timer expired | `tick_scheduler._release_retry_calls()` |
| 3 | `WAITING_DEPENDENCY` | `HALTED_APPROVAL` | All deps ended, requires approval | `call_fsm.request_approval()` |
| 4 | `WAITING_DEPENDENCY` | `WAITING_QUEUE` | All deps ended, no approval needed | `call_fsm.enqueue_after_dependencies()` |
| 5 | `WAITING_DEPENDENCY` | `ENDED_CANCELLED` | A dependency failed/stopped | `call_fsm.cancel()` |
| 6 | `WAITING_DEPENDENCY` | `ENDED_STOPPED` | External stop | `call_fsm.stop()` |
| 7 | `HALTED_APPROVAL` | `WAITING_QUEUE` | User approved | `call_fsm.approve()` |
| 8 | `HALTED_APPROVAL` | `ENDED_CANCELLED` | User denied | `call_fsm.cancel()` |
| 9 | `WAITING_QUEUE` | `ACTIVE_QUEUED` | Scheduler picks it up | `call_fsm.pick_up()` in `start_new_taskrun` |
| 10 | `WAITING_QUEUE` | `ENDED_CANCELLED` | Cancelled in queue | `call_fsm.cancel()` |
| 11 | `WAITING_QUEUE` | `ENDED_STOPPED` | Stopped in queue | `call_fsm.stop()` |
| 12 | `ACTIVE_QUEUED` | `WAITING_QUEUE` | Recovery — run was lost | `call_fsm.re_queue()` |
| 13 | `ACTIVE_QUEUED` | `ACTIVE_RUNNING` | Worker starts execution | `call_fsm.start_running()` |
| 14 | `ACTIVE_QUEUED` | `ENDED_CANCELLED` | Cancelled before run | `call_fsm.cancel()` |
| 15 | `ACTIVE_QUEUED` | `ENDED_STOPPED` | Stopped before run | `call_fsm.stop()` |
| 16 | `ACTIVE_RUNNING` | `ENDED_SUCCESS` | Run completed, no hooks | `call_fsm.succeed()` |
| 17 | `ACTIVE_RUNNING` | `WAITING_SUBTASKS_OR_HOOKS` | Run completed, has after-hooks | `call_fsm.wait_for_hooks()` |
| 18 | `ACTIVE_RUNNING` | `WAITING_RETRY` | Run failed, retries remain | `call_fsm.schedule_retry()` |
| 19 | `ACTIVE_RUNNING` | `ENDED_FAILURE_EXCEPTION` | Run failed, no retries left | `call_fsm.fail()` |
| 20 | `ACTIVE_RUNNING` | `WAITING_RATELIMIT` | Run hit LLM rate limit | `call_fsm.rate_limit()` |
| 21 | `WAITING_SUBTASKS_OR_HOOKS` | `WAITING_SUBTASKS_OR_HOOKS` | Self-loop — hook completed, more hooks pending | `call_fsm.wait_for_hooks()` |
| 22 | `WAITING_SUBTASKS_OR_HOOKS` | `ENDED_SUCCESS` | All hooks completed | `call_fsm.succeed()` |
| 23 | `WAITING_SUBTASKS_OR_HOOKS` | `ENDED_FAILURE_EXCEPTION` | Hook failed | `call_fsm.fail()` |
| 24 | `WAITING_SUBTASKS_OR_HOOKS` | `ENDED_CANCELLED` | Hook stopped | `call_fsm.cancel()` |
| 25 | `WAITING_SUBTASKS_OR_HOOKS` | `ENDED_STOPPED` | External stop | `call_fsm.stop()` |
| 26 | `WAITING_RATELIMIT` | `WAITING_QUEUE` | Rate limit released | `call_fsm.release_rate_limit()` |
| 27 | `WAITING_RATELIMIT` | `ENDED_CANCELLED` | Cancelled while rate-limited | `call_fsm.cancel()` |
| 28 | `WAITING_RATELIMIT` | `ENDED_STOPPED` | Stopped while rate-limited | `call_fsm.stop()` |
| 29 | `NEW` | `ENDED_CANCELLED` | Cancelled before processing | `call_fsm.cancel()` |
| 30 | `NEW` | `ENDED_STOPPED` | Stopped before processing | `call_fsm.stop()` |
| 31 | `WAITING_RETRY` | `ENDED_CANCELLED` | Cancelled during retry wait | `call_fsm.cancel()` |
| 32 | `WAITING_RETRY` | `ENDED_STOPPED` | Stopped during retry wait | `call_fsm.stop()` |

## Named Transition Methods

All methods return `True` if the update was applied, `False` on race (row already in a different state).

### `enter_dependency_wait(call_id)` (line 187)
Accepts both `NEW` and `WAITING_RETRY` as from-states via `__in`. Atomic.

### `request_approval(call_id)` (line 211)
`WAITING_DEPENDENCY → HALTED_APPROVAL`. Extra filter: `~Q(is_approved=True) & Q(requires_approval=True)`. Returns `False` if approval not required.

### `enqueue_after_dependencies(call_id)` (line 226)
`WAITING_DEPENDENCY → WAITING_QUEUE`. Extra filter: `Q(is_approved=True) | Q(requires_approval=False)`.

### `approve(call_id)` (line 241)
`HALTED_APPROVAL → WAITING_QUEUE`. Sets `is_approved=True`.

### `pick_up(call_id)` (line 251)
`WAITING_QUEUE → ACTIVE_QUEUED`.

### `re_queue(call_id)` (line 260)
`ACTIVE_QUEUED → WAITING_QUEUE`. Recovery path for lost Celery runs.

### `start_running(call_id)` (line 269)
`ACTIVE_QUEUED → ACTIVE_RUNNING`. Paired with Run `QUEUED → ACTIVE`.

### `wait_for_hooks(call_id, result_run_id)` (line 284)
Accepts both `ACTIVE_RUNNING` and `WAITING_SUBTASKS_OR_HOOKS` as from-states. Sets `taskcall_result_run_id`.

### `succeed(call_id, result_run_id)` (line 310)
Accepts both `ACTIVE_RUNNING` and `WAITING_SUBTASKS_OR_HOOKS` as from-states. Sets `ended_at=now()`.

### `schedule_retry(call_id, retry_delay_seconds, max_retries)` (line 336)
`ACTIVE_RUNNING → WAITING_RETRY`. Extra filter: `Q(retry_count__lt=max_retries)`. Atomically increments `retry_count` via `F()` and sets `dont_start_before`.

### `fail(call_id)` (line 356)
Accepts both `ACTIVE_RUNNING` and `WAITING_SUBTASKS_OR_HOOKS`. Sets `ended_at=now()`.

### `cancel(call_id, from_detail)` (line 376)
Returns `False` if `from_detail` has no valid path to `ENDED_CANCELLED` in `_VALID_TRANSITIONS`.

### `stop(call_id, from_detail)` (line 394)
Returns `False` if `from_detail` has no valid path to `ENDED_STOPPED`.

### `rate_limit(call_id)` (line 407)
`ACTIVE_RUNNING → WAITING_RATELIMIT`. Does not consume retry budget.

### `release_rate_limit(call_id)` (line 422)
`WAITING_RATELIMIT → WAITING_QUEUE`. Called when LLM capacity returns.
