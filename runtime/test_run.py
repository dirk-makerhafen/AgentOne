"""Smoke-test runner for a provider/model.

Creates a real (but invisible) test session that runs one turn with only the
``final_result`` tool advertised, so a single click validates the whole path:
HTTP transport, auth, model id, tool-call parsing and the ingest pipeline.
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.session_enums import SessionType
from server.models.enums.task_enums import TaskCallStatus
from server.models.providers.ai_model import AiModel
from server.models.queries.response import Response, ResponseStatus
from server.models.settings import (
    AgentToolCallSyntax,
    ReasoningEffort,
    ResponseTemperature,
    SettingsModel,
)
from server.models.sessions.session import SessionModel
from runtime.final_result import extract_final_result_text
from runtime.session.session import Session


KEEP_TEST_SESSIONS = 20
TEST_TIMEOUT_SECONDS = 90.0
TEST_PROMPT = (
    "Hi. If you can read this, call the final_result tool with content "
    "exactly 'yes'. Do not reply with plain text."
)


def _pick_test_agent() -> AgentModel:
    """Return an agent whose toolset includes ``final_result``."""
    for name in ("agentone", "coding", "general-chat"):
        agent = AgentModel.objects.filter(name=name).first()
        if agent is None:
            continue
        try:
            rt = agent.get_runtime()
            if any(getattr(t, "task_definition", None) is not None
                   and t.task_definition.name == "final_result"
                   for t in (rt.allowedTools or [])):
                return agent
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    for agent in AgentModel.objects.all().order_by("pk"):
        try:
            if agent.latest_agent_version is not None:
                return agent
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    raise RuntimeError("No agent available for model smoke test")


def _purge_old_test_sessions(keep: int = KEEP_TEST_SESSIONS) -> int:
    """Delete the oldest test sessions beyond *keep*. Returns count deleted."""
    from runtime.session_folder import session_dir

    qs = SessionModel.objects.filter(session_type=SessionType.TEST.value).order_by("-created_at")
    keep_ids = set(qs.values_list("pk", flat=True)[:keep])
    to_delete = list(qs.exclude(pk__in=keep_ids).values_list("pk", flat=True))
    deleted = 0
    for pk in to_delete:
        try:
            SessionModel.objects.filter(pk=pk).delete()
            deleted += 1
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        # Best-effort folder cleanup; startup sweep covers stragglers.
        try:
            d = session_dir(pk)
            if d.exists():
                import shutil
                shutil.rmtree(d, ignore_errors=True)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return deleted


def run_model_test(model_pk: int, *, timeout: float = TEST_TIMEOUT_SECONDS, keep: int = KEEP_TEST_SESSIONS) -> dict[str, Any]:
    """Run one smoke-test turn for *model_pk*. Returns a result dict."""
    started = time.monotonic()
    model = AiModel.objects.select_related("api_provider").get(pk=model_pk)
    provider = model.api_provider

    agent = _pick_test_agent()
    agent_version = agent.latest_agent_version
    if agent_version is None:
        raise RuntimeError(f"Agent {agent.name} has no version")

    ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    name = f"[test] {provider.name}/{model.name} {ts}"

    sv = agent_version.get_or_create_session(
        name=name,
        description=f"Smoke test for {provider.name}/{model.name}",
        session_type=SessionType.TEST.value,
        group_key=f"test:model:{model.pk}",
        settings_overrides={
            "aimodel": model,
            "tool_call_syntax": AgentToolCallSyntax.DEFAULT.value,
            "tool_call_allowlist": ["final_result"],
            "reasoning_effort": ReasoningEffort.MINIMAL.value,
            "max_turns": 3,
            "precision": ResponseTemperature.PRECISE.value,
        },
    )

    session = Session(session_model=sv.session, pinned_session_version=sv)

    call = None
    try:
        call = session.add_user_message(TEST_PROMPT, force=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _purge_old_test_sessions(keep)
        return _failed_result(model, provider, session, sv, started, "exception", str(exc))

    # Wait for the turn to end.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            fresh = type(call).objects.get(pk=call.pk)
        except Exception:  # pylint: disable=broad-exception-caught
            break
        if fresh.status in (
            TaskCallStatus.ENDED,
            TaskCallStatus.FAILED,
            TaskCallStatus.CANCELLED,
            TaskCallStatus.RATE_LIMITED,
        ):
            break
        time.sleep(1.0)

    latency_ms = int((time.monotonic() - started) * 1000)

    # Resolve the result message.
    result_msg = None
    try:
        if call is not None:
            result_msg = call.get_result(timeout=0)
    except Exception:  # pylint: disable=broad-exception-caught
        result_msg = None

    # Token counts from the last Response row.
    tokens = {"prompt": 0, "completion": 0}
    try:
        resp = Response.objects.filter(session_version=sv).order_by("-pk").first()
        if resp is not None:
            tokens["prompt"] = int(resp.prompt_tokens or 0)
            tokens["completion"] = int(resp.completion_tokens or 0)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Determine verdict.
    verdict = "no_tool_call"
    answer = ""
    error_kind = None
    error_message = ""

    call_status = None
    try:
        if call is not None:
            call_status = type(call).objects.get(pk=call.pk).status
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    if call_status in (TaskCallStatus.FAILED, TaskCallStatus.CANCELLED, TaskCallStatus.RATE_LIMITED):
        verdict = "failed"
        # Try to read a response-level error.
        try:
            resp = Response.objects.filter(session_version=sv).order_by("-pk").first()
            if resp is not None:
                error_kind = (resp.error_type or "").strip() or None
                error_message = (resp.error_message or "").strip()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        if not error_message:
            error_message = str(call_status)
    else:
        text = extract_final_result_text(result_msg) if result_msg is not None else ""
        answer = text.strip()
        if text.strip():
            verdict = "healthy"
        else:
            # Distinguish "no tool call" from "model errored mid-run".
            try:
                resp = Response.objects.filter(session_version=sv).order_by("-pk").first()
                if resp is not None and resp.status == ResponseStatus.FAILURE:
                    verdict = "failed"
                    error_kind = (resp.error_type or "").strip() or None
                    error_message = (resp.error_message or "").strip() or "request failed"
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    # Mark the session inactive/archived-ish (keep inspectable).
    try:
        sv.session.is_active = False
        sv.session.save(update_fields=["is_active", "updated_at"])
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    _purge_old_test_sessions(keep)

    return {
        "ok": verdict == "healthy",
        "verdict": verdict,
        "answer": answer,
        "model": model.name,
        "provider": provider.name,
        "model_pk": model.pk,
        "session_pk": sv.session.pk,
        "latency_ms": latency_ms,
        "tokens": tokens,
        "error_kind": error_kind,
        "error_message": error_message,
        "tested_at": timezone.now().isoformat(),
    }


def _failed_result(model, provider, session, sv, started, error_kind, error_message):
    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        sv.session.is_active = False
        sv.session.save(update_fields=["is_active", "updated_at"])
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    _purge_old_test_sessions(KEEP_TEST_SESSIONS)
    return {
        "ok": False,
        "verdict": "failed",
        "answer": "",
        "model": model.name,
        "provider": provider.name,
        "model_pk": model.pk,
        "session_pk": getattr(sv.session, "pk", None),
        "latency_ms": latency_ms,
        "tokens": {"prompt": 0, "completion": 0},
        "error_kind": error_kind,
        "error_message": error_message,
        "tested_at": timezone.now().isoformat(),
    }


def best_usable_model(provider_pk: int) -> AiModel | None:
    """Pick the best model on a provider for a smoke test."""
    from runtime.rate_limiter import RateLimitChecker

    provider = None
    try:
        provider = AiModel.objects.filter(api_provider_id=provider_pk).first().api_provider
    except Exception:  # pylint: disable=broad-exception-caught
        from server.models.providers.api_provider import ApiProvider
        provider = ApiProvider.objects.filter(pk=provider_pk).first()
    if provider is None:
        return None

    candidates = list(
        AiModel.objects.filter(api_provider=provider, enabled=True).order_by("pk")
    )
    if not candidates:
        return None

    # Filter cooling-down / hard-failed rows.
    usable = []
    for m in candidates:
        if m.status in ("UNAVAILABLE", "AUTH_ERROR"):
            continue
        try:
            limited, _ = m.is_rate_limited()
            if limited:
                continue
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        usable.append(m)

    pool = usable or candidates
    # Prefer healthy/unknown, then by pk.
    def sort_key(m):
        status = getattr(m, "status", "") or ""
        rank = 0 if status in ("HEALTHY", "UNKNOWN", "") else 1
        return (rank, m.pk)
    pool.sort(key=sort_key)
    return pool[0]
