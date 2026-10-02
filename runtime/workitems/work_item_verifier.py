"""Agent verification of completed work items.

Mirrors the approval auto-review in
:mod:`runtime.tasks.call_scheduler` (``_dispatch_auto_review`` /
``auto_review_approval`` / ``_launch_review_brief``): a separate agent session
receives a brief of evidence and calls back a verdict tool.  Nothing is
decided by parsing the reviewer's prose.

Two properties are inherited deliberately:

* **The pull model.** The reviewer calls ``workitem_verdict``; the framework
  never guesses what it meant.
* **Fail-safe.** Any failure leaves the item ``in_review`` for a human.  It
  never auto-approves, because a silently-approved item is indistinguishable
  from a good one.

And one is imposed here, because the work layer has no equivalent in the
approval flow: the brief must not be built from the ATC status alone.  A tool
that crashes returns ``(False, {'status': 'exception', ...})`` and the call
still ends ``ENDED_SUCCESS`` — green is exactly what failure looks like
(``docs/work-items.md`` §3.1-3.2).
"""
from __future__ import annotations

import json
from typing import Any

from django.utils import timezone

#: Assistant messages copied into the brief.  Bounded on purpose: the reviewer
#: gets a fresh context, and an unbounded transcript would make verification
#: cost more than the work it is checking.
BRIEF_MESSAGE_LIMIT = 10

#: Per-call result payload cap in the brief.
BRIEF_RESULT_LIMIT = 2000

#: Tool-name cap per call line in the brief.
BRIEF_TOOLNAME_LIMIT = 60

#: The note that keeps a reviewer from misreading a green call as a success.
#: Mirrors ``runtime/tasks/bound_task.py``'s ``except`` branch, which returns
#: ``(False, {'status': 'exception', 'message': traceback})`` and then lets the
#: run take the SUCCESS path.
TOOL_ERROR_CONVENTION = (
    "IMPORTANT — how to read tool results below. A tool that crashes is caught "
    "and returned as a normal value: (False, {'status': 'exception', 'message': "
    "<traceback>}). The framework records that call as SUCCESS, because the tool "
    "was invoked and produced a result. So a SUCCESS status is NOT evidence that "
    "the work succeeded. Judge the payloads themselves: any 'status': 'exception' "
    "entry, or a result that reports an error in prose, is a FAILURE of that step "
    "even though the call is green."
)


class WorkItemVerifier:
    """Launches and drives the ``work_verifier`` agent.

    A static-only namespace: every operation is a classmethod-style helper.
    """

    # pylint: disable=R0903
    @staticmethod
    def verify(work_item_id: int) -> None:
        """Review one work item on a worker.

        Dispatched by ``_verify_work_items`` after the item has been marked
        ``verify_status="pending"``.  Builds the brief, spawns a
        ``work_verifier`` session and sends the brief; the reviewer's
        ``workitem_verdict`` tool applies the outcome.
        """
        from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus
        from server.models.workitems.work_item import WorkItem

        item = WorkItem.objects.filter(pk=work_item_id).first()
        if item is None:
            return
        if item.status != WorkItemStatus.IN_REVIEW:
            return  # a human (or another process) already decided
        if item.verify_status != WorkItemVerifyStatus.PENDING:
            return  # already dispatched or decided

        try:
            executor_session = WorkItemVerifier._executor_session(item)
            if executor_session is None:
                raise RuntimeError("work item has no executor session")
            brief = WorkItemVerifier._build_verification_brief(item)
            WorkItemVerifier._launch_reviewer_session(item, executor_session, brief)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Fail-safe: surface the failure to the human, never auto-approve.
            print(
                f"workitem_verify: review of item #{work_item_id} failed "
                f"-> escalate: {exc}"
            )
            WorkItem.objects.filter(pk=item.pk).update(
                verify_status=WorkItemVerifyStatus.ESCALATED,
                verify_reason=f"Verification failed: {exc}",
                updated_at=timezone.now(),
            )

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    @staticmethod
    def _executor_session(item: Any) -> Any:
        """Return the executor ``Session``, or ``None``."""
        from runtime.session.session import Session

        if not item.executor_session_id or not item.executor_session:
            return None
        return Session(session_model=item.executor_session)

    @staticmethod
    def _build_verification_brief(item: Any) -> str:
        """Compose the evidence brief handed to the reviewer.

        Carries the requirement, the executor's own words, and the per-call
        result payloads — deliberately *not* a bare "the call succeeded" signal.
        See :data:`TOOL_ERROR_CONVENTION`.
        """
        lines = [
            "Review the work below and render your verification verdict.",
            "",
            f"Work item id: {item.pk}  "
            "(copy this exact number verbatim into your workitem_verdict call)",
            f"Title: {item.title or '(untitled)'}",
            "",
            "REQUIREMENT — the work that was asked for:",
            "```",
            (item.body or "(no body given)").strip(),
            "```",
            "",
            "WHAT THE EXECUTOR REPORTED (its own final_result, if any):",
            "```",
            WorkItemVerifier._final_result_text(item) or "(the executor called no final_result)",
            "```",
        ]

        messages = WorkItemVerifier._recent_assistant_texts(item)
        if messages:
            lines += ["", "THE EXECUTOR'S LAST MESSAGES:"]
            for i, text in enumerate(messages, start=1):
                lines += [f"--- message {i} ---", "```", text, "```"]

        calls = WorkItemVerifier._call_summaries(item)
        if calls:
            lines += ["", "TOOL CALLS MADE BY THE EXECUTOR (payloads are the evidence):"]
            lines += calls

        lines += [
            "",
            "NOTE ON STATUS DETAIL: the dispatch ended with "
            f"status_detail={item.root_task.status_detail if item.root_task_id and item.root_task else 'unknown'}. "
            "Treat this as a routing hint only, NOT as a success signal — see below.",
            "",
            TOOL_ERROR_CONVENTION,
            "",
            "Decide whether the executor actually produced what the requirement "
            "asked for. Judge the requirement, not the process: ordinary "
            "imperfections are not grounds for rejection, but an unfulfilled or "
            "falsely-reported requirement is.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _final_result_text(item: Any) -> str:
        """Return the executor's ``final_result`` content, or ``""``."""
        try:
            from server.models.tasks.agent_task_call import AgentTaskCall

            if not item.root_task_id or not item.root_task:
                return ""
            call = AgentTaskCall.objects.filter(
                session_root_task=item.root_task, task_definition__name="final_result"
            ).order_by("-created_at").first()
            if call is None or not call.taskcall_result_run:
                return ""
            return str(call.taskcall_result_run.result_json or "")[:BRIEF_RESULT_LIMIT]
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    @staticmethod
    def _recent_assistant_texts(item: Any) -> list[str]:
        """Return the executor's last N assistant message texts."""
        from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole

        if not item.executor_session_id:
            return []
        try:
            from server.models.message import Message, MessagePart

            messages = Message.objects.filter(
                session=item.executor_session, role=MessageRole.ASSISTANT
            ).order_by("-created_at")[:BRIEF_MESSAGE_LIMIT]
            texts: list[str] = []
            for message in messages:
                parts = MessagePart.objects.filter(message=message).order_by("created_at")
                for part in parts:
                    if part.type == MessagePartType.MESSAGE and part.content_type == MessageContentType.TEXT:
                        content = getattr(part.content, "content", None)
                        if content:
                            texts.append(str(content)[:BRIEF_RESULT_LIMIT])
            return list(reversed(texts))
        except Exception:  # pylint: disable=broad-exception-caught
            return []

    @staticmethod
    def _call_summaries(item: Any) -> list[str]:
        """Return one bounded line per tool call in the dispatch's call tree.

        The tree is reached via ``session_root_task``, which every call in a
        turn points at — the same root the executor session ran under.  The
        root call itself is matched explicitly: its ``session_root_task`` points
        elsewhere, so filtering on that column alone would silently drop the
        very call whose ``status_detail`` and payload we most need to see.
        """
        from django.db.models import Q

        from server.models.tasks.agent_task_call import AgentTaskCall

        if not item.root_task_id or not item.root_task:
            return []
        try:
            calls = (
                AgentTaskCall.objects.filter(
                    Q(session_root_task=item.root_task) | Q(pk=item.root_task_id)
                )
                .order_by("created_at")
                .distinct()
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return []

        lines: list[str] = []
        for call in calls:
            name = call.task_definition.name if call.task_definition_id else "(unknown)"
            run = call.taskcall_result_run
            payload = run.result_json if run else None
            lines.append(
                f"- {name} [{call.status_detail}] :: {_truncate(_render(payload), BRIEF_RESULT_LIMIT)}"
            )
        return lines

    # ------------------------------------------------------------------
    # Reviewer session
    # ------------------------------------------------------------------

    # Spawning a child session with per-run settings needs a lot of locals;
    # splitting it would only hide the sequence of steps.
    # pylint: disable=R0914
    @staticmethod
    def _launch_reviewer_session(item: Any, executor_session: Any, brief: str) -> Any:
        """Spawn a ``work_verifier`` session to review *item*.

        Returns the child :class:`Session`.  The child session's settings
        declare ``verify_work_item_id`` so the reviewer's verdict tool can
        validate the id it echoes back — a hallucinated id can never approve the
        wrong work item.
        """
        from time import time_ns

        from server.models.agents.agent import AgentModel
        from server.models.enums.message_enums import MessageContentType, MessagePartType
        from server.models.enums.session_enums import SessionType
        from server.models.settings import SettingsModel
        from server.models.sessions.session_version import SessionVersionModel
        from runtime.session.session import Session

        verifier = AgentModel.objects.filter(name=WorkItemVerifier.REVIEWER_AGENT_NAME).first()
        if verifier is None:
            raise RuntimeError(f"{WorkItemVerifier.REVIEWER_AGENT_NAME} agent not loaded")

        # No self-review: an agent grading its own output is self-certification
        # and would make the verdict decorative.
        if item.assigned_agent_id and item.assigned_agent_id == verifier.pk:
            raise RuntimeError(
                f"{WorkItemVerifier.REVIEWER_AGENT_NAME} is also the executor of "
                f"item #{item.pk}; refusing self-review"
            )

        verifier_av = verifier.get_runtime().get_version_model()
        child_sv = verifier_av.get_or_create_session(
            name=f"workitem-review:{item.pk}:{time_ns()}",
            display_name=f"Verification of work item #{item.pk}",
            description=brief[:100],
            workspace=executor_session.workspace,
            parent_session_version=executor_session.get_version_model(),
            session_type=SessionType.SUBTASK_FORK,
        )

        # Declare the review target on the child session settings.
        settings = SettingsModel(extra_settings={"verify_work_item_id": item.pk})
        settings.save()
        SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=settings)

        child_session = Session(
            session_model=child_sv.session, pinned_session_version=child_sv
        )
        now = timezone.localtime().strftime("%Y-%m-%d %H:%M")
        working_dir = (
            child_session.workspace.path if child_session.workspace else "unknown"
        )
        parts = [
            {
                "type": MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": f"It is now {now}, your working dir is '{working_dir}'.\n",
            },
            {
                "type": MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": (
                    "You are the Work Verifier checking whether a piece of work "
                    "actually meets its requirement. Analyse the brief, then call "
                    "workitem_verdict once with your decision. The verdict ends "
                    "this review session — no final_result needed.\n\n" + brief
                ),
            },
        ]
        child_session.add_user_message(parts=parts)
        return child_session

    #: Agent that renders verdicts.  Resolved by name so the reviewer can be
    #: swapped without touching this module.
    REVIEWER_AGENT_NAME = "work_verifier"


def _truncate(text: str, limit: int) -> str:
    """Clamp *text* to *limit* characters, marking that it was cut."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated at {limit} chars]"


def _render(payload: Any) -> str:
    """Render a call's result payload as readable text."""
    if payload is None:
        return "(no result)"
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return str(payload)
