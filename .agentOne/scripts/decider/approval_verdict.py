"""
`approval_verdict` — the single decision tool of the `approval_decider` agent.

The decider reviews a pending python/shell approval and calls this tool once.
The verdict is applied to the *parent* call (the one the review brief was
about), which is identified by ``task_call_id`` and cross-checked against the
decider session's declared review target so a hallucinated id can never
approve the wrong call.

Verds are applied as follows:

- ``allow`` → the parent call is approved and scheduled for execution.
- ``deny``   → the parent call is cancelled and the denial (with the reason)
  is fed back to the requesting agent via ``catch_approval_denied``.
- ``ask_human`` → the parent call stays ``HALTED_APPROVAL`` for a human.

Any invalid / ambiguous verdict falls back to ``ask_human`` (fail-safe).
"""

from __future__ import annotations

from typing import Any, Literal

from server.models.enums.task_enums import TaskCallStatusDetail

Decision = Literal["allow", "deny", "ask_human"]
_VALID_DECISIONS = ("allow", "deny", "ask_human")


# pylint: disable=too-many-return-statements
def approval_verdict(
    _session: Any,
    decision: Decision,
    reason: str = "",
    task_call_id: int = 0,
) -> tuple[bool, dict]:
    """
    Apply an automated approval decision to a pending python/shell call.

    Args:
        _session: The approval_decider session (bound, injected).
        decision: One of "allow", "deny", "ask_human".
        reason: Short justification for the decision.
        task_call_id: The id of the pending call this verdict applies to; it
            must match the review target declared on this session.

    Returns:
        A ``(True, dict)`` result carrying the link ``decision``, ``applied``
        (whether the verdict took effect) and any ``note`` explaining why a
        verdict could not be applied.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall

    if decision not in _VALID_DECISIONS:
        return _verdict_result(decision, False, note=f"Unknown decision {decision!r}; escalated to human.")

    expected = _review_target(_session)
    if task_call_id != expected:
        return _verdict_result(
            decision,
            False,
            note=f"task_call_id {task_call_id} does not match review target {expected}; escalated to human.",
        )

    call = AgentTaskCall.objects.filter(pk=task_call_id).first()
    if call is None:
        return _verdict_result(decision, False, note="Call not found; escalated to human.")

    tool_name = call.task_definition.name if call.task_definition else ""
    if tool_name not in ("python", "shell"):
        return _verdict_result(
            decision, False, note=f"Call is {tool_name!r}, not python/shell; escalated to human."
        )

    if call.auto_review_status in ("approved", "denied", "escalated"):
        return _verdict_result(
            decision,
            False,
            note=f"Call already decided ({call.auto_review_status}); not re-applied.",
        )

    if call.status_detail != TaskCallStatusDetail.HALTED_APPROVAL:
        return _verdict_result(
            decision,
            False,
            note=f"Call no longer awaiting approval (status: {call.status_detail}); "
            "human may have already decided.",
        )

    return _apply_verdict(call, decision, reason)


def _review_target(_session: Any) -> int:
    """Return the review target call id declared on the decider session.

    Reads the child session's settings straight from the DB (never a cached
    instance attribute), so the mapping set by the auto-review launcher is
    always honoured.
    """
    try:
        from server.models.sessions.session_version import SessionVersionModel
        from server.models.settings import SettingsModel

        sv = _session.get_version_model()
        latest = (
            SessionVersionModel.objects.filter(pk=sv.pk)
            .values("session_settings")
            .first()
            if sv and sv.pk
            else None
        )
        if not latest or not latest["session_settings"]:
            return 0
        settings = SettingsModel.objects.filter(pk=latest["session_settings"]).first()
        extra = settings.extra_settings if settings else None
        return int((extra or {}).get("review_task_call_id", 0) or 0)
    except Exception:  # pylint: disable=broad-exception-caught
        return 0


def _apply_verdict(call: Any, decision: str, reason: str) -> tuple[bool, dict]:
    from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
    from runtime.tasks.call_scheduler import CallScheduler

    if decision == "allow":
        # Approve + record the verdict on the same call row.
        _ATC.objects.filter(pk=call.pk).update(
            auto_review_status="approved", auto_review_reason=reason or ""
        )
        CallScheduler.approve_taskcall(call.pk)
        return _verdict_result(decision, True, note="Approved automatically.")

    if decision == "deny":
        _ATC.objects.filter(pk=call.pk).update(
            auto_review_status="denied", auto_review_reason=reason or ""
        )
        denied = CallScheduler.deny_taskcall(call.pk, feedback=reason or "")
        return _verdict_result(decision, denied, note="Denied automatically." if denied else "Deny failed; left halted.")

    # ask_human — leave paused so the human card remains.
    _ATC.objects.filter(pk=call.pk).update(auto_review_status="escalated", auto_review_reason=reason or "")
    return _verdict_result(decision, True, note="Escalated to human.")


def _verdict_result(decision: str, applied: bool, note: str) -> tuple[bool, dict]:
    return True, {
        "decision": decision,
        "applied": applied,
        "note": note,
    }
