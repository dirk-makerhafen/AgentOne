"""Ask the user structured questions and wait for their answers.

Use this tool when you hit a genuine decision fork that only the user can
resolve — ambiguous requirements, architecture trade-offs, or a choice
between valid approaches where guessing would cause rework. Do NOT use it
for routine confirmations ("may I proceed?"), permission requests, or
questions the codebase already answers.

How it works: calling this tool pauses your turn and renders your questions
as clickable options in the user's chat. The turn resumes automatically once
the user answers, and their answers arrive as this tool's result. If the
user declines instead, you receive an error telling you to proceed with your
best judgment.

Rules (following the AskUserQuestion / MCP-elicitation conventions):
- Ask 1-4 questions per call with concrete, mutually exclusive options.
- Each question needs 2-4 options. Every option needs a short ``label``
  (1-5 words) and a ``description`` explaining the trade-off in 1-2
  sentences. Put every selectable choice in ``options`` — never only in
  the question prose.
- Put the recommended option first and suffix its label with
  " (Recommended)".
- Keep ``header`` to 12 characters max (short tab/chip label).
- Set ``multiSelect: true`` only when several options may legitimately
  apply at once.
- The user can always answer with free text ("Other") — you do not need to
  add an Other option yourself.
- NEVER ask for secrets (passwords, API keys, tokens) with this tool.
- One question per call is preferred unless several answers must be
  submitted together.
"""

from typing import Any, Optional, TypedDict

from runtime.session.session import Session
from runtime.user_questions import (
    format_answers_for_llm,
    normalize_questions,
    validate_answers,
    validate_questions,
)


class AskOption(TypedDict):
    """One selectable choice (label plus trade-off description)."""

    label: str
    description: str


class AskQuestion(TypedDict):
    """One question with 2-4 discrete options."""

    question: str
    header: str
    options: list[AskOption]
    multiSelect: bool


def ask_user(
    _session: Session,
    questions: list[AskQuestion],
    answers: Optional[dict[str, Any]] = None,
) -> tuple[bool, dict[str, Any]]:
    """Ask the user questions; resume with their answers.

    Args:
        questions: 1-4 question objects, each with question (full text
            ending with '?'), header (max 12 chars), options (2-4 objects
            with label and description), and multiSelect (true only when
            several options may apply at once).
        answers: Reserved for the user's answers. DO NOT supply this
            argument — it is filled in by the question card before your
            call is allowed to execute.

    Returns:
        ``(True, {"status": "success", "answers": ..., "summary": ...})``
        with answers keyed by question text, or ``(False, {"status":
        "error", "message": ...})`` when the call is malformed or the user
        declined (proceed with best judgment in that case).
    """
    ok, reason = validate_questions(questions)
    if not ok:
        return False, {"status": "error", "message": reason}

    if not answers:
        return False, {
            "status": "error",
            "message": (
                "No user answers were recorded for these questions. "
                "If the user declined to answer, proceed with your best "
                "judgment instead of asking again."
            ),
        }

    normalized_questions = normalize_questions(questions)
    ok, reason, normalized = validate_answers(normalized_questions, answers)
    if not ok:
        return False, {"status": "error", "message": reason}
    return True, {
        "status": "success",
        "answers": normalized,
        "summary": format_answers_for_llm(normalized),
    }
