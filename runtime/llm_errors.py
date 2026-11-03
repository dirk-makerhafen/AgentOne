"""Classify LLM/provider exceptions into actionable failure kinds.

The runtime needs to distinguish three very different situations that all
arrive as exceptions:

* **transient capacity/availability** — 429/503/timeouts (park and retry),
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

import litellm


#: Health status values (mirrors ``server.models.enums.provider_enums.HealthStatus``).
#: Kept as strings so this module does not depend on Django being configured.
HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_RATE_LIMITED = "RATE_LIMITED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
HEALTH_AUTH_ERROR = "AUTH_ERROR"
HEALTH_CONFIG_ERROR = "CONFIG_ERROR"

_RATE_LIMIT_STATUS = {429, 503}
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


def _is_rate_limit(exc, status_code: int | None, message: str) -> bool:
    if status_code in _RATE_LIMIT_STATUS:
        return True
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
    if isinstance(exc, litellm.exceptions.NotFoundError):
        return True
    lower = message.lower()
    return "model_not_found" in lower or (
        "model" in lower and "does not exist" in lower
    )


def _is_auth(exc, status_code: int | None) -> bool:
    if status_code in (401, 403):
        return True
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

    if status_code == 408 or isinstance(exc, litellm.Timeout):
        return LLMErrorInfo(
            kind="timeout",
            message=message,
            status_code=status_code,
            retry_after=retry_after_seconds,
            scope="model",
            health_status=HEALTH_DEGRADED,
        )

    if status_code in (400, 422) or isinstance(exc, litellm.exceptions.BadRequestError):
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

    if isinstance(exc, litellm.exceptions.APIConnectionError):
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
