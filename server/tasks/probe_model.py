"""Celery task: smoke-test a provider/model via a real test session."""
from __future__ import annotations

import json
from typing import Any

from celery import shared_task
from django.core.cache import cache

from server.models.providers.ai_model_offering import AiModelOffering as AiModel
from runtime.test_run import run_model_test


PROBE_CACHE_TTL = 3600  # 1 hour


def _cache_key(model_pk: int) -> str:
    return f"agentone:probe:model:{model_pk}"


def _running_key(model_pk: int) -> str:
    return f"agentone:probe:running:{model_pk}"


@shared_task(name="tasks.probe_model")
def probe_model(model_pk: int) -> dict[str, Any]:
    """Run a smoke test for *model_pk* and publish the result."""
    running_key = _running_key(model_pk)
    # Dedup: if a probe is already running, return its cached (running) state.
    if cache.get(running_key):
        cached = cache.get(_cache_key(model_pk))
        if cached is not None:
            return cached
        return {"verdict": "running", "model_pk": model_pk}

    cache.set(running_key, True, timeout=PROBE_CACHE_TTL)
    try:
        result = run_model_test(model_pk)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        result = {
            "ok": False,
            "verdict": "failed",
            "answer": "",
            "model_pk": model_pk,
            "session_pk": None,
            "latency_ms": 0,
            "tokens": {"prompt": 0, "completion": 0},
            "error_kind": "exception",
            "error_message": str(exc),
            "tested_at": None,
        }
    finally:
        cache.delete(running_key)

    cache.set(_cache_key(model_pk), result, timeout=PROBE_CACHE_TTL)

    # Publish so subscribed views re-render.
    try:
        AiModel.publish_by_pk(model_pk, "update", data={"probe": result})
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    return result


def get_cached_result(model_pk: int) -> dict[str, Any] | None:
    return cache.get(_cache_key(model_pk))


def is_running(model_pk: int) -> bool:
    return bool(cache.get(_running_key(model_pk)))
