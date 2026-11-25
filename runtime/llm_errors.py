"""Classify LLM/provider exceptions into actionable failure kinds.

The runtime needs to distinguish three very different situations that all
arrive as exceptions:

* **transient capacity/availability** — 429/503/timeouts (park and retry),
  except inference-server faults (e.g. OMLX cache corruption) that merely
  arrive as a synthetic 503 — those are real server failures,
* **sticky model/config failures** — 404 model id, 401/403 auth, unsupported
  model parameters (skip the row until it is fixed or re-tested),
* **request failures** — a 400 caused by the prompt (context length, bad
  image, ...) that must *not* poison the model's health.

A single classification is also stored on ``Response.error_type`` so failures
are auditable without scraping tracebacks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def _litellm():
    """Import ``litellm`` lazily.

    ``litellm`` pulls in the whole provider/openai type tree and costs several
    seconds to import.  This module is imported during Django app startup
    (``server.admin`` -> ``agent_task_run`` -> ``runtime.rate_limiter``), but
    the library is only needed when an actual provider error is classified.
    Keeping the import inside the helpers avoids paying that cost before the
    web server starts accepting requests.
    """
    import litellm  # pylint: disable=import-outside-toplevel

    return litellm


#: Health status values (mirrors ``server.models.enums.provider_enums.HealthStatus``).
#: Kept as strings so this module does not depend on Django being configured.
HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_RATE_LIMITED = "RATE_LIMITED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
HEALTH_AUTH_ERROR = "AUTH_ERROR"
HEALTH_CONFIG_ERROR = "CONFIG_ERROR"

_RATE_LIMIT_STATUS = {429, 503}

# Mid-stream failures from local inference servers can be wrapped by litellm
# in ``MidStreamFallbackError``, a ``ServiceUnavailableError`` subclass with a
# synthetic 503.  They are *not* capacity exhaustion: parking the provider key
# just retries the same broken request until the cooldown caps out.  Match the
# server's own diagnostic text so genuine 429/503 failures stay rate limits.
_PROVIDER_FAULT_HINTS = (
    "cache corruption",
    "broadcast_shapes",
    "cannot be broadcast",
)
_CONFIG_HINTS = (
    "invalid model",
    "model not supported",
    "does not support",
    "unsupported model",
    "unsupported parameter",
    "invalid parameter",
    "unknown parameter",
    "model_not_found",
)


class ModelUnavailableError(Exception):
    """Raised when a model row is known-unusable and should be skipped.

    Deliberately **not** a ``RateLimitError``: a 404 model id or a revoked key
    will not recover by waiting, so the task must fail instead of parking.
    """


@dataclass(frozen=True)
class LLMErrorInfo:  # pylint: disable=too-many-instance-attributes
    """Structured view of one provider failure."""

    kind: str
    message: str
    status_code: int | None = None
    retry_after: float | None = None
    scope: str = "request"  # request | model | key | provider
    health_status: str = ""
    sticky: bool = False
    config_like: bool = False


def _iter_chain(exc):
    """Yield *exc* and its wrapped causes without looping."""
    seen: set[int] = set()
    candidate = exc
    while candidate is not None and id(candidate) not in seen:
        seen.add(id(candidate))
        yield candidate
        candidate = (
            getattr(candidate, "original_exception", None)
            or getattr(candidate, "__cause__", None)
        )


def _status_code(exc) -> int | None:
    for candidate in _iter_chain(exc):
        for attr in ("status_code", "code", "http_status"):
            raw = getattr(candidate, attr, None)
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if 100 <= value <= 599:
                return value
        response = getattr(candidate, "response", None)
        if response is not None:
            try:
                value = int(getattr(response, "status_code", 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if 100 <= value <= 599:
                return value
    return None


def _messages(exc) -> str:
    parts: list[str] = []
    for candidate in _iter_chain(exc):
        message = getattr(candidate, "message", "") or ""
        text = str(candidate)
        if message:
            parts.append(str(message))
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts)[:4000]


def extract_retry_after_seconds(exc) -> float | None:
    """Return the cooldown the provider asked for, in seconds.

    Precedence:
      1. litellm ``RateLimitError.response.headers[Retry-After]``.
      2. ``Retry-After`` on the wrapped ``httpx.Response``.
      3. Text embedded in the error message — Google reports
         ``Please retry in 58.184175815s`` and ``"retryDelay": "58s"``.
    """
    try:
        for candidate in _iter_chain(exc):
            response = getattr(candidate, "response", None)
            for source in (
                getattr(response, "headers", None),
                getattr(candidate, "headers", None),
            ):
                if source is None:
                    continue
                retry_after = source.get("retry-after") or source.get("Retry-After")
                if retry_after:
                    try:
                        return max(1.0, float(retry_after))
                    except (TypeError, ValueError):
                        pass
        message = _messages(exc)
        patterns = (
            r"retry in ([\d.]+)s",
            r'"retryDelay"\s*:\s*"?([\d.]+)s',
            r"retry[\s_-]*after[\s:=(]*([\d.]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    return max(1.0, float(match.group(1)))
                except (TypeError, ValueError):
                    continue
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    return None


def _is_provider_fault(message: str) -> bool:
    """True for inference-server faults that must not be billed as rate limits.

    OMLX/MLX reports a corrupt KV cache mid-stream as ``Cache corruption not
    recoverable after retries: [broadcast_shapes]``.  litellm wraps that in a
    ``MidStreamFallbackError`` (a 503 ``ServiceUnavailableError``), which would
    otherwise park the only API key and make every waiting task retry forever.
    """
    lower = (message or "").lower()
    return any(hint in lower for hint in _PROVIDER_FAULT_HINTS)


def _is_rate_limit(exc, status_code: int | None, message: str) -> bool:
    if status_code in _RATE_LIMIT_STATUS:
        return True
    litellm = _litellm()
    if isinstance(
        exc,
        (
            litellm.exceptions.RateLimitError,
            litellm.exceptions.ServiceUnavailableError,
            litellm.Timeout,
        ),
    ):
        return True
    for candidate in _iter_chain(exc):
        if isinstance(
            candidate,
            (
                litellm.exceptions.RateLimitError,
                litellm.exceptions.ServiceUnavailableError,
                litellm.Timeout,
            ),
        ):
            return True
    # Vertex AI wraps 429 as BadRequestError; detect via string patterns.
    return bool(
        re.search(r'"code"\s*:\s*429', message)
        or "RESOURCE_EXHAUSTED" in message
    )


def _is_model_not_found(exc, status_code: int | None, message: str) -> bool:
    if status_code == 404:
        return True
    if isinstance(exc, _litellm().exceptions.NotFoundError):
        return True
    lower = message.lower()
    return "model_not_found" in lower or (
        "model" in lower and "does not exist" in lower
    )


def _is_auth(exc, status_code: int | None) -> bool:
    if status_code in (401, 403):
        return True
    litellm = _litellm()
    if isinstance(
        exc,
        (
            litellm.exceptions.AuthenticationError,
            litellm.exceptions.PermissionDeniedError,
        ),
    ):
        return True
    return any(
        isinstance(
            candidate,
            (
                litellm.exceptions.AuthenticationError,
                litellm.exceptions.PermissionDeniedError,
            ),
        )
        for candidate in _iter_chain(exc)
    )


def _looks_like_config(message: str) -> bool:
    lower = message.lower()
    return any(hint in lower for hint in _CONFIG_HINTS)


def classify_llm_error(  # pylint: disable=too-many-return-statements
    exc, retry_after_seconds: float | None = None
) -> LLMErrorInfo:
    """Classify *exc* into a failure kind, scope and suggested health state."""
    status_code = _status_code(exc)
    message = _messages(exc)
    lower = message.lower()

    # Check before the 503/MidStreamFallbackError rate-limit branch: a broken
    # local inference server needs a real failure (and a degraded health mark),
    # not a key cooldown that silently retries the same request for an hour.
    if _is_provider_fault(message):
        return LLMErrorInfo(
            kind="server",
            message=message,
            status_code=status_code,
            retry_after=None,
            scope="model",
            health_status=HEALTH_DEGRADED,
        )

    if _is_rate_limit(exc, status_code, message):
        return LLMErrorInfo(
            kind="rate_limit",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="key",
            health_status=HEALTH_RATE_LIMITED,
        )

    if _is_model_not_found(exc, status_code, message):
        return LLMErrorInfo(
            kind="model_not_found",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model",
            health_status=HEALTH_UNAVAILABLE,
            sticky=True,
        )

    if _is_auth(exc, status_code):
        return LLMErrorInfo(
            kind="auth",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="key",
            health_status=HEALTH_AUTH_ERROR,
            sticky=True,
        )

    if status_code == 408 or isinstance(exc, _litellm().Timeout):
        return LLMErrorInfo(
            kind="timeout",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model",
            health_status=HEALTH_DEGRADED,
        )

    if status_code in (400, 422) or isinstance(exc, _litellm().exceptions.BadRequestError):
        config_like = _looks_like_config(message)
        return LLMErrorInfo(
            kind="bad_request",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model" if config_like else "request",
            health_status=HEALTH_CONFIG_ERROR if config_like else "",
            config_like=config_like,
        )

    if status_code is not None and 500 <= status_code < 600:
        return LLMErrorInfo(
            kind="server",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model",
            health_status=HEALTH_DEGRADED,
        )

    if isinstance(exc, _litellm().exceptions.APIConnectionError):
        return LLMErrorInfo(
            kind="connection",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model",
            health_status=HEALTH_DEGRADED,
        )

    return LLMErrorInfo(
        kind="unknown",
        message=message or lower,
        status_code=status_code,
        retry_after=retry_after_seconds,
    )
