# Paired ATC-Run Lifecycle

The `AgentTaskCall` (ATC) and `AgentTaskRun` (Run) are updated together at key points. Race conditions are handled via atomic `WHERE status=X` updates.

## 1. Run Start (Worker Picks Up)

**Code:** `RunScheduler._apply_async(run_id)` (`run_scheduler.py:22-42`)

```
1. run_fsm.start(run_id)                # QUEUED → ACTIVE
2. call_fsm.start_running(call_id)       # ACTIVE_QUEUED → ACTIVE_RUNNING
3. If step 2 fails:
     run_fsm.rollback_to_queued(run_id)  # ACTIVE → QUEUED
```

**Race condition:** Two workers receive the same Celery message. Worker A starts the run (`QUEUED → ACTIVE`). Worker B's `start()` returns False (run already ACTIVE). Worker B exits. Worker A proceeds to `start_running()`. If another process already transitioned the ATC out of `ACTIVE_QUEUED`, Worker A rolls back the run to `QUEUED`.

## 2. Run Completes (Positive, No Result Refs)

**Code:** `RunScheduler._apply_async()` → `apply()` → `run_scheduler.py:71-72`

```
1. apply() returns normally, no ref_pks
2. run_fsm.succeed(run_id)              # ACTIVE → SUCCESS
3. CallScheduler.on_taskrun_ended():
   a. No after-hooks:
      call_fsm.succeed(call_id)          # ACTIVE_RUNNING → ENDED_SUCCESS
   b. Has after-hooks:
      call_fsm.wait_for_hooks(call_id)   # ACTIVE_RUNNING → WAITING_SUBTASKS_OR_HOOKS
```

## 3. Run Completes (With Result Refs / CHAIN)

**Code:** `run_scheduler.py:54-66`

```
1. apply() returns WAITING_RESULTTASKS (ref_pks non-empty)
2. Check pending refs:
   a. Refs still pending:
      call_fsm.wait_for_hooks()           # ACTIVE_RUNNING → WAITING_SUBTASKS_OR_HOOKS
   b. No refs pending (all already ended):
      all_taskrun_result_references_ended()
```

## 4. Run Fails (No Retries)

**Code:** `call_scheduler.on_taskrun_ended()` (`call_scheduler.py:275-282`)

```
1. apply() raises exception → FAILURE
2. call_fsm.schedule_retry():
   a. Retries remain → WAITING_RETRY (return)
   b. No retries left → call_fsm.fail()  # ACTIVE_RUNNING → ENDED_FAILURE_EXCEPTION
```

## 5. Run Hits Rate Limit

**Code:** `run_scheduler.py:46-52`

```
1. apply() catches RateLimitError → RATE_LIMITED (raw set, bypasses FSM)
2. call_fsm.rate_limit(call_id)          # ACTIVE_RUNNING → WAITING_RATELIMIT
```

## 6. Run in WAITING_RESULTTASKS — A Ref Ends

**Code:** `run_scheduler.taskrun_result_reference_ended()` (`run_scheduler.py:79-101`)

```
1. result_taskcall_ended(status):
   a. Status != ENDED_SUCCESS:
      run_fsm.fail(run_id)               # WAITING_RESULTTASKS → FAILURE
   b. Status == ENDED_SUCCESS, more refs pending: return
   c. Status == ENDED_SUCCESS, no refs pending:
      all_taskrun_result_references_ended()
```

## Sequence Diagrams

### Happy Path (No Hooks)

```mermaid
sequenceDiagram
    participant CS as CallScheduler
    participant RS as RunScheduler
    participant ATC as AgentTaskCall
    participant Run as AgentTaskRun

    CS->>ATC: pick_up() → ACTIVE_QUEUED
    CS->>Run: create(NEW) + apply_async()
    RS->>Run: enqueue() → QUEUED
    RS->>Run: start() → ACTIVE
    RS->>ATC: start_running() → ACTIVE_RUNNING
    Run->>Run: apply() → SUCCESS
    RS->>Run: succeed() → SUCCESS
    RS->>CS: on_taskrun_ended(SUCCESS)
    CS->>ATC: succeed() → ENDED_SUCCESS
```

### CHAIN Execution

```mermaid
sequenceDiagram
    participant CS as CallScheduler
    participant RS as RunScheduler
    participant ATC as AgentTaskCall
    participant Run as AgentTaskRun
    participant Child as ChildATC

    CS->>ATC: pick_up() → ACTIVE_QUEUED
    RS->>ATC: start_running() → ACTIVE_RUNNING
    Run->>Run: apply() → CHAIN mode
    Run->>Child: create + apply_async() (×N)
    Run->>Run: WAITING_RESULTTASKS
    RS->>ATC: wait_for_hooks() → WAITING_SUBTASKS_OR_HOOKS
    Note over Child,RS: Children execute...
    Child-->>RS: ENDED_SUCCESS
    RS->>Run: succeed() → SUCCESS
    RS->>CS: on_taskrun_ended(SUCCESS)
    CS->>ATC: succeed() → ENDED_SUCCESS
```

### Error: Run Fails + Retry

```mermaid
sequenceDiagram
    participant Run as AgentTaskRun
    participant RS as RunScheduler
    participant CS as CallScheduler
    participant ATC as AgentTaskCall

    Run->>Run: apply() → FAILURE
    RS->>CS: on_taskrun_ended(FAILURE)
    CS->>ATC: schedule_retry() → WAITING_RETRY
    Note over ATC: retry_count++, dont_start_before set
    Note over ATC: [time passes]
    CS->>ATC: enter_dependency_wait() → WAITING_DEPENDENCY
    CS->>ATC: enqueue_after_dependencies() → WAITING_QUEUE
    CS->>Run: start_new_taskrun → NEW Run
```

### ATC Ended Propagation

When any ATC reaches `ENDED`, `_on_taskcall_ended()` (`call_scheduler.py:375-501`) propagates the result to three groups of dependents:

```mermaid
flowchart LR
    A[ATC ENDED] --> B{Propagate to}
    B --> C[Parent Runs<br/>WAITING_RESULTTASKS]
    B --> D[Dependent ATCs<br/>WAITING_DEPENDENCY]
    B --> E[Hook-Parent ATCs<br/>WAITING_SUBTASKS_OR_HOOKS]
    C --> F[RunScheduler.<br/>taskrun_result_reference_ended]
    D --> G[CallScheduler.<br/>on_arg_reference_task_ended]
    E --> H[CallScheduler.<br/>on_posthook_ended]
```

Additionally, if the ATC terminated successfully, `taskcall_on_success_callbacks` are dispatched. On failure, `taskcall_on_error_callbacks` are dispatched. Finally, the queue is drained (per-TI parallel limit and per-session ingest FIFO).
