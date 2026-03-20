from __future__ import annotations
from server.models.enums.task_enums import TaskRunStatus
 
 
# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: frozenset[tuple[TaskRunStatus, TaskRunStatus]] = frozenset({
    (TaskRunStatus.NEW,                 TaskRunStatus.QUEUED),
    (TaskRunStatus.QUEUED,              TaskRunStatus.ACTIVE),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.WAITING_RESULTTASKS),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.SUCCESS),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.FAILURE),
    (TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.SUCCESS),
    (TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE),
})
 
 
class InvalidTransition(Exception):
    pass
 
 
class TaskRunStateMachine:
    """
    Single entry point for all AgentTaskRun status transitions.
 
    Replaces AgentTaskRunRuntime._set_status() and the two raw .update() calls
    in _apply_async. TaskRun state is simpler than TaskCall — no approval gates,
    retries, or hooks. Those live at the TaskCall level.
 
        NEW → QUEUED → ACTIVE → SUCCESS
                              → FAILURE
                              → WAITING_RESULTTASKS → SUCCESS
                                                    → FAILURE
    """
 
    @staticmethod
    def transition(
        run_id: int,
        from_status: TaskRunStatus,
        to_status: TaskRunStatus,
        extra: dict | None = None,
    ) -> bool:
        """
        Core atomic transition. Prefer the named methods below at call sites.
 
        Returns True if updated, False on race condition.
        Raises InvalidTransition if the pair is not in _VALID_TRANSITIONS.
        """
        if (from_status, to_status) not in _VALID_TRANSITIONS:
            raise InvalidTransition(
                f"Invalid AgentTaskRun transition: {from_status} → {to_status}"
            )
        from server.models.tasks.agent_task_run import AgentTaskRun
 
        fields = {"status": to_status}
        if extra:
            fields.update(extra)
 
        return AgentTaskRun.objects.filter(pk=run_id, status=from_status).update(**fields) > 0
 
    # ------------------------------------------------------------------
    # Named transition methods
    # ------------------------------------------------------------------
 
    @staticmethod
    def enqueue(run_id: int) -> bool:
        """NEW → QUEUED (run created and submitted to the worker queue)."""
        return TaskRunStateMachine.transition(run_id, TaskRunStatus.NEW, TaskRunStatus.QUEUED)
 
    @staticmethod
    def start(run_id: int) -> bool:
        """
        QUEUED → ACTIVE.
        Called from run_runtime._apply_async paired with the taskcall
        ACTIVE_QUEUED → ACTIVE_RUNNING update. If this succeeds but the
        taskcall update fails, the caller must roll this back to QUEUED.
        """
        return TaskRunStateMachine.transition(run_id, TaskRunStatus.QUEUED, TaskRunStatus.ACTIVE)
 
    @staticmethod
    def rollback_to_queued(run_id: int) -> bool:
        """
        ACTIVE → QUEUED.
        Used in run_runtime._apply_async when the paired taskcall
        ACTIVE_QUEUED → ACTIVE_RUNNING update fails (race condition).
        This is the only reverse transition in the system.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun
        # Not in _VALID_TRANSITIONS deliberately — this is an exceptional rollback,
        # not a normal flow step. We do it directly.
        return AgentTaskRun.objects.filter(
            pk=run_id, status=TaskRunStatus.ACTIVE
        ).update(status=TaskRunStatus.QUEUED) > 0
 
    @staticmethod
    def wait_for_results(run_id: int) -> bool:
        """
        ACTIVE → WAITING_RESULTTASKS.
        The run returned successfully but its result_json contains AgentTaskCall
        references that haven't finished yet. Stays open until all referenced
        calls reach ENDED (tracked by taskrun_result_references M2M).
        """
        return TaskRunStateMachine.transition(
            run_id, TaskRunStatus.ACTIVE, TaskRunStatus.WAITING_RESULTTASKS
        )
 
    @staticmethod
    def succeed(run_id: int) -> bool:
        """
        ACTIVE or WAITING_RESULTTASKS → SUCCESS.
        Tries WAITING_RESULTTASKS first (all referenced calls just finished),
        falls back to ACTIVE (no result references were involved).
        """
        succeeded = TaskRunStateMachine.transition(
            run_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.SUCCESS
        )
        if not succeeded:
            succeeded = TaskRunStateMachine.transition(
                run_id, TaskRunStatus.ACTIVE, TaskRunStatus.SUCCESS
            )
        return succeeded
 
    @staticmethod
    def fail(run_id: int) -> bool:
        """
        WAITING_RESULTTASKS or ACTIVE → FAILURE.
        Tries WAITING_RESULTTASKS first (a referenced call failed), falls back
        to ACTIVE (the run itself raised an exception).
        """
        failed = TaskRunStateMachine.transition(
            run_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE
        )
        if not failed:
            failed = TaskRunStateMachine.transition(
                run_id, TaskRunStatus.ACTIVE, TaskRunStatus.FAILURE
            )
        return failed