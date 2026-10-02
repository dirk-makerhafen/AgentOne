"""
`workitem_verdict` — the single decision tool of the `work_verifier` agent.

The reviewer checks a finished work item against its requirement and calls this
tool once.  The verdict is applied to the *work item* the brief was about,
identified by ``work_item_id`` and cross-checked against the reviewer session's
declared target so a hallucinated id can never approve the wrong work.

Verdicts are applied as follows:

- ``approve``    → the item becomes ``done`` and is marked approved.
- ``reject``     → the item is blocked with the reason, and one verify attempt
  is consumed.  Past ``MAX_VERIFY_ATTEMPTS`` the rejection is converted into an
  escalation, so a reviewer that keeps rejecting cannot ping-pong an item
  between a human and an agent forever.
- ``ask_human``  → the item stays ``in_review`` for a human to decide.

Any invalid / ambiguous verdict falls back to ``ask_human`` (fail-safe).
"""

from __future__ import annotations

from typing import Any, Literal

from server.models.workitems.enums import WorkItemStatus

Decision = Literal["approve", "reject", "ask_human"]
_VALID_DECISIONS = ("approve", "reject", "ask_human")


# pylint: disable=too-many-return-statements
def workitem_verdict(
    _session: Any,
    work_item_id: int,
    decision: Decision,
    reason: str,
) -> tuple[bool, dict]:
    """
    Apply a verification decision to the work item you were asked to review.

    Call this exactly once, after you have read the brief, with the work item
    id copied verbatim from it. The verdict ends this review session.

    Judge the *requirement*, not the process: ordinary imperfections are not
    grounds for rejection, but work that does not meet the stated requirement
    is.

    Args:
        _session: The work_verifier session (bound, injected).
        work_item_id: The id of the work item under review, copied exactly
            from "Work item id:" in the brief. It is cross-checked against the
            target declared on this session, so a misread id cannot decide a
            different item.
        decision: "approve" — the work meets the requirement, so the item
            completes. "reject" — it does not, so the item is blocked with your
            reason and returned to a human for rework. "ask_human" — the
            evidence is not conclusive, so escalate rather than guess.
        reason: One or two sentences justifying the decision, written for the
            human who will act on it. This is the only record of why the item
            was accepted or sent back.

    Returns:
        A ``(True, dict)`` result. The outer ``True`` only means the tool ran;
        check ``applied`` to see whether the verdict actually changed anything.
        The dict carries ``decision``, ``applied`` and a ``note`` describing
        the outcome.

        Anything unusable — an id that is not the review target, an
        unrecognised decision, missing evidence — is escalated to a human on
        the review target rather than dropped, so the item cannot be left
        waiting forever. ``applied`` is ``False`` in that case only if the
        escalation itself could not be written.
    """
    from server.models.workitems.work_item import WorkItem

    expected = _review_target(_session)
    if not expected:
        return _verdict_result(
            decision,
            False,
            note="No review target is declared on this session; nothing was "
            "decided. A human must pick this item up.",
        )

    if work_item_id != expected:
        return _fail_safe(
            expected,
            f"Reviewer passed work_item_id {work_item_id}, which is not the "
            f"review target {expected}.",
        )

    if decision not in _VALID_DECISIONS:
        return _fail_safe(expected, f"Reviewer passed unknown decision {decision!r}.")

    item = WorkItem.objects.filter(pk=work_item_id).first()
    if item is None:
        return _verdict_result(decision, False, note="Work item not found; nothing to decide.")

    if not item.requires_verification:
        return _verdict_result(
            decision, False, note="Work item does not require verification; not applied."
        )

    if item.verify_status in ("approved", "rejected", "escalated"):
        return _verdict_result(
            decision,
            False,
            note=f"Work item already decided ({item.verify_status}); not re-applied.",
        )

    if item.status != WorkItemStatus.IN_REVIEW:
        return _verdict_result(
            decision,
            False,
            note=f"Work item no longer awaiting review (status: {item.status}); "
            "a human may have already decided.",
        )

    return _apply_verdict(item, decision, reason)


def _review_target(_session: Any) -> int:
    """Return the work item id declared on the reviewer session.

    Reads the child session's settings straight from the DB (never a cached
    instance attribute), so the mapping set by the verifier launcher is always
    honoured.
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
        return int((extra or {}).get("verify_work_item_id", 0) or 0)
    except Exception:  # pylint: disable=broad-exception-caught
        return 0


def _apply_verdict(item: Any, decision: str, reason: str) -> tuple[bool, dict]:
    from runtime.workitems.workitem_fsm import WorkItemStateMachine

    if decision == "approve":
        if WorkItemStateMachine.approve(item.pk, reason):
            return _verdict_result(decision, True, note="Approved automatically.")
        return _verdict_result(
            decision, False, note="Item was no longer approvable; not applied."
        )

    if decision == "reject":
        # reject_or_escalate consumes a verify attempt and escalates instead
        # once the budget is gone.
        status = WorkItemStateMachine.reject_or_escalate(item.pk, reason)
        if status == "escalated":
            return _verdict_result(
                decision,
                True,
                note="Rejected, but the verify-attempt budget is spent; escalated to a human.",
            )
        return _verdict_result(decision, True, note="Rejected; blocked for rework.")

    # ask_human — stay in review so a human can decide.
    if WorkItemStateMachine.escalate(item.pk, reason or "reviewer could not decide"):
        return _verdict_result(decision, True, note="Escalated to human.")
    return _verdict_result(
        decision, False, note="Item was no longer awaiting review; not applied."
    )


def _fail_safe(expected: int, why: str) -> tuple[bool, dict]:
    """Escalate *expected* to a human, or admit that could not be done.

    A garbled verdict must not leave the item sitting in ``in_review`` with a
    ``pending`` verification that nothing will ever clear — the tick only
    claims items whose ``verify_status`` is NULL, so a stranded item is
    invisible to both the scheduler and the reviewer. Escalating is the
    fail-safe, and the note reports whether it actually landed rather than
    claiming an escalation that never happened.
    """
    from runtime.workitems.workitem_fsm import WorkItemStateMachine

    if WorkItemStateMachine.escalate(expected, f"Verification inconclusive: {why}"):
        return _verdict_result(
            None, True, note=f"{why} Escalated to a human for decision."
        )
    return _verdict_result(
        None,
        False,
        note=f"{why} Escalation could not be written either — a human must "
        f"look at work item {expected} directly.",
    )


def _verdict_result(decision: str | None, applied: bool, note: str) -> tuple[bool, dict]:
    return True, {
        "decision": decision,
        "applied": applied,
        "note": note,
    }
