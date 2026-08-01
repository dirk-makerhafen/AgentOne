# Code Reference

Key code locations with line numbers. All paths relative to the repository root.

## State Machine Definitions

| Path | Lines | Content |
|---|---|---|
| `runtime/tasks/call_fsm.py` | 11-81 | `_VALID_TRANSITIONS` — all 32 valid ATC state transitions |
| `runtime/tasks/call_fsm.py` | 110-448 | `TaskCallStateMachine` — all named transition methods |
| `runtime/tasks/call_fsm.py` | 187-208 | `enter_dependency_wait()` — NEW/WAITING_RETRY → WAITING_DEPENDENCY |
| `runtime/tasks/call_fsm.py` | 211-223 | `request_approval()` — WAITING_DEPENDENCY → HALTED_APPROVAL |
| `runtime/tasks/call_fsm.py` | 226-238 | `enqueue_after_dependencies()` — WAITING_DEPENDENCY → WAITING_QUEUE |
| `runtime/tasks/call_fsm.py` | 241-248 | `approve()` — HALTED_APPROVAL → WAITING_QUEUE |
| `runtime/tasks/call_fsm.py` | 251-257 | `pick_up()` — WAITING_QUEUE → ACTIVE_QUEUED |
| `runtime/tasks/call_fsm.py` | 260-266 | `re_queue()` — ACTIVE_QUEUED → WAITING_QUEUE |
| `runtime/tasks/call_fsm.py` | 269-296 | `start_running()` — ACTIVE_QUEUED → ACTIVE_RUNNING (guards against root ENDED) |
| `runtime/tasks/call_fsm.py` | 299-323 | `wait_for_hooks()` — ACTIVE_RUNNING/WAITING_SUBTASKS_OR_HOOKS → WAITING_SUBTASKS_OR_HOOKS |
| `runtime/tasks/call_fsm.py` | 325-349 | `succeed()` — ACTIVE_RUNNING/WAITING_SUBTASKS_OR_HOOKS → ENDED_SUCCESS |
| `runtime/tasks/call_fsm.py` | 351-369 | `schedule_retry()` — ACTIVE_RUNNING → WAITING_RETRY (with F increment) |
| `runtime/tasks/call_fsm.py` | 371-389 | `fail()` — ACTIVE_RUNNING/WAITING_SUBTASKS_OR_HOOKS → ENDED_FAILURE_EXCEPTION |
| `runtime/tasks/call_fsm.py` | 391-407 | `cancel()` — stateful → ENDED_CANCELLED |
| `runtime/tasks/call_fsm.py` | 409-420 | `stop()` — stateful → ENDED_STOPPED |
| `runtime/tasks/call_fsm.py` | 422-435 | `rate_limit()` — ACTIVE_RUNNING → WAITING_RATELIMIT |
| `runtime/tasks/call_fsm.py` | 437-448 | `release_rate_limit()` — WAITING_RATELIMIT → WAITING_QUEUE |
| `runtime/tasks/run_fsm.py` | 9-18 | `_VALID_TRANSITIONS` — all valid Run state transitions (incl. ACTIVE→RATE_LIMITED) |
| `runtime/tasks/run_fsm.py` | 37-224 | `TaskRunStateMachine` — all named transition methods |
| `runtime/tasks/run_fsm.py` | 104-106 | `enqueue()` — NEW → QUEUED |
| `runtime/tasks/run_fsm.py` | 109-117 | `start()` — QUEUED → ACTIVE |
| `runtime/tasks/run_fsm.py` | 120-136 | `rollback_to_queued()` — ACTIVE → QUEUED (NOT in _VALID_TRANSITIONS) |
| `runtime/tasks/run_fsm.py` | 139-154 | `wait_for_results()` — ACTIVE → WAITING_RESULTTASKS |
| `runtime/tasks/run_fsm.py` | 157-177 | `succeed()` — WAITING_RESULTTASKS/ACTIVE → SUCCESS |
| `runtime/tasks/run_fsm.py` | 180-206 | `fail()` — WAITING_RESULTTASKS/ACTIVE → FAILURE |

## Models

| Path | Lines | Content |
|---|---|---|
| `server/models/tasks/agent_task_call.py` | 1-187 | ATC model definition (fields, create, apply_async) |
| `server/models/tasks/agent_task_call.py` | 188-337 | ATC create_call_arguments_json, _resolve_call_arguments, get_result |
| `server/models/tasks/agent_task_run.py` | 1-146 | Run model definition (fields, create, apply_async) |
| `server/models/tasks/agent_task_run.py` | 147-229 | `apply()` — execution logic (CHAIN, GROUP, MAP, FUNCTION) |
| `server/models/tasks/agent_task_run.py` | 214-218 | `rate_limit()` FSM transition → `RATE_LIMITED` (no longer a raw update) |
| `server/models/enums/task_enums.py` | 1-59 | All enum definitions (TaskCallStatus, TaskCallStatusDetail, TaskRunStatus) |
| `server/models/tasks/task_instance.py` | 1-250 | TaskInstance model (get_or_create, apply_async, create_call) |

## Call Scheduler

| Path | Lines | Content |
|---|---|---|
| `runtime/tasks/call_scheduler.py` | 20-38 | `_apply_async()` — ATC entry point |
| `runtime/tasks/call_scheduler.py` | 44-86 | `on_arg_reference_task_ended()` — dependency resolution |
| `runtime/tasks/call_scheduler.py` | 88-115 | `on_all_arg_reference_tasks_ended()` — after all deps resolved |
| `runtime/tasks/call_scheduler.py` | 117-192 | Guardrail checks (shell, python) |
| `runtime/tasks/call_scheduler.py` | 198-204 | `approve_taskcall()` — human approval |
| `runtime/tasks/call_scheduler.py` | 211-266 | `start_new_taskrun()` — admission control (row-lock per TI) + dispatch; `_pick_up_and_create_run()` at 250-266 |
| `runtime/tasks/call_scheduler.py` | 259-313 | `on_taskrun_ended()` — handle run completion |
| `runtime/tasks/call_scheduler.py` | 315-356 | `on_posthook_ended()` — hook completion |
| `runtime/tasks/call_scheduler.py` | 358-368 | `on_all_on_posthook_ended()` — all hooks done |
| `runtime/tasks/call_scheduler.py` | 375-518 | `_on_taskcall_ended()` — ATC finalisation + propagation (sweeps stranded runs) |
| `runtime/tasks/call_scheduler.py` | 502-511 | Per-TI drain (release next WAITING_QUEUE) |
| `runtime/tasks/call_scheduler.py` | 513-517 | Per-session ingest FIFO drain |
| `runtime/tasks/call_scheduler.py` | 520-572 | `_cancel_safe()` — force cancellation; raises `RuntimeError` on unhandled state |
| `runtime/tasks/call_scheduler.py` | 574-603 | `cancel_root_tasktree()` — cancel entire root turn (deepest-first) |
| `runtime/tasks/call_scheduler.py` | 605-615 | `_release_next_queued_call()` — session-level release |

## Run Scheduler

| Path | Lines | Content |
|---|---|---|
| `runtime/tasks/run_scheduler.py` | 22-73 | `_apply_async()` — paired run+call start |
| `runtime/tasks/run_scheduler.py` | 36-37 | Run QUEUED → ACTIVE |
| `runtime/tasks/run_scheduler.py` | 39-41 | Call ACTIVE_QUEUED → ACTIVE_RUNNING + rollback |
| `runtime/tasks/run_scheduler.py` | 46-52 | RATE_LIMITED handling (call → WAITING_RATELIMIT) |
| `runtime/tasks/run_scheduler.py` | 54-66 | WAITING_RESULTTASKS handling |
| `runtime/tasks/run_scheduler.py` | 79-101 | `taskrun_result_reference_ended()` — ref resolution |
| `runtime/tasks/run_scheduler.py` | 103-119 | `all_taskrun_result_references_ended()` — all refs done |

## Tick Scheduler (10s Periodic)

| Path | Lines | Content |
|---|---|---|
| `server/tasks/tick_scheduler.py` | 36-44 | `tick_scheduler()` — main entry, tick structure |
| `server/tasks/tick_scheduler.py` | 49-88 | `_release_rate_limited_calls()` — LLM capacity recovery |
| `server/tasks/tick_scheduler.py` | 91-110 | `_release_retry_calls()` — retry timer recovery |
| `server/tasks/tick_scheduler.py` | 113-128 | `_release_scheduled_calls()` — scheduled dispatch |
| `server/tasks/tick_scheduler.py` | 132-141 | `_process_cron_jobs()` — cron dispatch |
| `server/tasks/tick_scheduler.py` | 481-534 | `_dispatch_data_flows()` — data flow dispatch |
| `server/tasks/tick_scheduler.py` | 537-593 | `_propagate_from_collections()` — collection propagation |

## Recovery Scheduler (60s Periodic + Startup)

| Path | Lines | Content |
|---|---|---|
| `server/tasks/recovery_scheduler.py` | 28-37 | `tick_scheduler_recovery()` — 60s recovery pass entry |
| `server/tasks/recovery_scheduler.py` | 39-50 | `startup_cleanup()` — one-time startup task (runs release/recover passes immediately) |
| `server/tasks/recovery_scheduler.py` | 52-77 | `_release_queued_calls()` — queue fallback drain (cancels dangling-ref calls) |
| `server/tasks/recovery_scheduler.py` | 79-102 | `_timeout_active_runs()` — time limit enforcement |
| `server/tasks/recovery_scheduler.py` | 104-191 | `_resolve_stuck_waiting_runs()` — deadlock recovery |
| `server/tasks/recovery_scheduler.py` | 136 | Case 1: all refs ended → resolve |
| `server/tasks/recovery_scheduler.py` | 143-183 | Case 2: no active refs → multi-level tree check + fail (grace or immediate) |
| `server/tasks/recovery_scheduler.py` | 194-362 | `_recover_stuck_calls()` — 6 recovery steps |
| `server/tasks/recovery_scheduler.py` | 206-235 | Step 1: ACTIVE_QUEUED → cancel if root ended, else re-queue orphan |
| `server/tasks/recovery_scheduler.py` | 237-248 | Step 2: QUEUED runs > 15min → re-dispatch |
| `server/tasks/recovery_scheduler.py` | 250-276 | Step 3: ACTIVE_RUNNING with no ACTIVE run → retry/fail |
| `server/tasks/recovery_scheduler.py` | 278-300 | Step 4: WAITING_SUBTASKS_OR_HOOKS with ended result run → resolve |
| `server/tasks/recovery_scheduler.py` | 302-329 | Step 5: WAITING_DEPENDENCY with all ended deps → resume |
| `server/tasks/recovery_scheduler.py` | 331-358 | Step 6: WAITING_QUEUE → per session, newest root's oldest child first (skip dangling-ref) |
| `server/tasks/recovery_scheduler.py` | 364-390 | `_references_query()` / `_has_dangling_call_refs()` — JSON ref helpers |
| `server/tasks/recovery_scheduler.py` | 393-451 | `_force_end_call()` — general termination |
| `server/tasks/recovery_scheduler.py` | 453-549 | `_cancel_duplicate_queries()` — query dedup |
| `server/tasks/recovery_scheduler.py` | 551-696 | `_recover_stale_queries()` — crash-recovery for queries |
| `server/tasks/recovery_scheduler.py` | 698-707 | `_cleanup_stale_runtime_folders()` — startup cleanup |

## Scripts (process_turn Chain)

| Path | Lines | Content |
|---|---|---|
| `.agentone/scripts/core/scripts.md` | 66-74 | `process_turn` CHAIN definition |
| `.agentone/scripts/core/ingest_user_message.py` | 1-62 | User message entry, chain linking |
| `.agentone/scripts/core/ingest_user_message.py` | 42 | `filter(next_messages=None).last()` — tail detection |
| `.agentone/scripts/core/ingest_assistant_message.py` | 1-80 | Assistant message creation, tool call dispatch |
| `.agentone/scripts/core/decide_next_step.py` | 1-59 | Turn decision logic (continue/stop) |
| `.agentone/scripts/core/decide_next_step.py` | 54 | `_is_subtask_execution` → `process_turn.delay()` |
| `.agentone/scripts/core/decide_next_step.py` | 59 | Default continue → `process_turn.delay()` |
