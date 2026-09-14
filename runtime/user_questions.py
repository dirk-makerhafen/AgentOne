"""Validation and normalisation for the ``ask_user`` question tool.

Best-practice synthesis (MCP elicitation ``elicitation/create``, Claude Code
``AskUserQuestion``, OpenClaw ``ask_user``):

- 1–4 questions per call; each question carries 2–4 discrete options with a
  short ``label`` plus a ``description`` explaining the trade-off.
- Optional short ``header`` (<=12 chars) for tab/chip display.
- Optional ``multiSelect`` for questions where several options may apply.
- Free-text answers are always accepted (the UI renders an "Other" input) —
  unknown labels validate as custom text, never as errors.
- Secrets (passwords, API keys, tokens) must never be requested this way.
- A declined/dismissed question means "proceed with best judgment", never a
  hard failure — the deny path reuses the approval-denial feedback.

The canonical question form produced by :func:`normalize_questions`::

    {"question": str, "header": str, "options": [{"label": str,
     "description": str}], "multiSelect": bool}

Answers are keyed by question text (Claude Code convention)::

    {"How should I format the output?": "Summary"}
    {"Which sections?": ["Introduction", "Conclusion"]}  # multiSelect
"""
from __future__ import annotations

from typing import Any

MAX_QUESTIONS = 4
MAX_OPTIONS = 4
MIN_OPTIONS = 2
MAX_HEADER_LEN = 12

ASK_USER_TOOL_NAME = "ask_user"


def normalize_questions(questions: Any) -> list[dict[str, Any]]:
    """Return the canonical form of *questions* (assumes valid)."""
    normalized: list[dict[str, Any]] = []
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        options = []
        for o in q.get("options") or []:
            if not isinstance(o, dict):
                continue
            options.append({
                "label": str(o.get("label", "")),
                "description": str(o.get("description", "")),
            })
        normalized.append({
            "question": str(q.get("question", "")),
            "header": str(q.get("header", ""))[:MAX_HEADER_LEN],
            "options": options,
            "multiSelect": bool(q.get("multiSelect", False)),
        })
    return normalized


def validate_questions(questions: Any) -> tuple[bool, str]:
    """Check the LLM-supplied ``questions`` argument.

    Returns:
        ``(True, "")`` when valid, else ``(False, reason)`` describing the
        first problem found (suitable for feeding back to the LLM).
    """
    if not isinstance(questions, list) or not questions:
        return False, "questions must be a non-empty list of 1-4 questions."
    if len(questions) > MAX_QUESTIONS:
        return False, (
            f"Ask at most {MAX_QUESTIONS} questions per call "
            f"(got {len(questions)}). Split the rest into a follow-up call."
        )
    for i, q in enumerate(questions):
        where = f"Question {i + 1}"
        if not isinstance(q, dict):
            return False, f"{where} must be an object with question/options."
        if not str(q.get("question", "")).strip():
            return False, f"{where} needs a non-empty question text."
        options = q.get("options")
        if not isinstance(options, list) or not (
            MIN_OPTIONS <= len(options) <= MAX_OPTIONS
        ):
            return False, (
                f"{where} needs {MIN_OPTIONS}-{MAX_OPTIONS} options "
                "(got "
                f"{len(options) if isinstance(options, list) else 'none'})."
            )
        for j, o in enumerate(options):
            if not isinstance(o, dict) or not str(o.get("label", "")).strip():
                return False, (
                    f"{where}, option {j + 1} needs a non-empty label."
                )
    return True, ""


def validate_answers(questions: list[dict[str, Any]], answers: Any) -> tuple[bool, str, dict[str, Any]]:
    """Check a user-supplied *answers* map against *questions*.

    Unknown labels are accepted as free-text ("Other") answers.  Unknown
    question keys and empty values are rejected.

    Returns:
        ``(ok, reason, normalized)`` where normalized maps question text to
        the selected label (single) or list of labels (multiSelect).
    """
    if not isinstance(answers, dict) or not answers:
        return False, "answers must be a non-empty object.", {}
    by_question = {q["question"]: q for q in questions}
    normalized: dict[str, Any] = {}
    for key, value in answers.items():
        q = by_question.get(key)
        if q is None:
            return False, f"Unknown question: {key!r}.", {}
        if q["multiSelect"]:
            values = value if isinstance(value, list) else [value]
            values = [str(v).strip() for v in values if str(v).strip()]
            if not values:
                return False, f"No answer given for {key!r}.", {}
            normalized[key] = values
        else:
            if isinstance(value, list):
                value = value[0] if value else ""
            text = str(value).strip()
            if not text:
                return False, f"No answer given for {key!r}.", {}
            normalized[key] = text
    return True, "", normalized


def all_answered(
    questions: list[dict[str, Any]], answers: dict[str, Any] | None
) -> bool:
    """Return whether every question has a non-empty answer."""
    if not answers:
        return False
    return all(
        bool(answers.get(q["question"]))
        if not isinstance(answers.get(q["question"]), list)
        else len(answers[q["question"]]) > 0
        for q in questions
    )


def format_answers_for_llm(answers: dict[str, Any]) -> str:
    """Render answers as ``"question"="answer"`` pairs for the tool result."""
    parts = []
    for question, answer in answers.items():
        text = ", ".join(answer) if isinstance(answer, list) else str(answer)
        parts.append(f'"{question}"="{text}"')
    return (
        "The user has answered your questions: " + "; ".join(parts) + ". "
        "Continue with these answers in mind."
    )
