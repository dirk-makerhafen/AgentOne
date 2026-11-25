"""Build the ordered candidate chain for a route intent.

The chain is deliberately explicit: every entry is a concrete
``(offering, optional api_key)`` pair plus a short reason, so the caller can
explain what was tried.  ``RateLimitChecker`` still performs admission on each
candidate; this module only decides *which* candidates are acceptable and in
what order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from django.db.models import Q
from django.db.models.functions import Coalesce

from runtime.routing.intent import (
    PIN_MODEL,
    PIN_OFFERING,
    PIN_OFFERING_KEY,
    RouteIntent,
)
from runtime.routing.quality import rank_satisfies, tier_max_rank

#: Hard cap on the chain length.  A full model→model ladder over every free
#: offering is pointless (and slow); the first handful of scored candidates is
#: plenty before the scheduler parks the call.
MAX_CHAIN = 16


@dataclass(frozen=True)
class Candidate:
    """One routable (offering, key) pair."""

    offering: Any
    api_key: Any = None
    reason: str = ""

    @property
    def label(self) -> str:
        provider = getattr(self.offering, "api_provider", None)
        provider_name = getattr(provider, "name", "") or "?"
        name = getattr(self.offering, "name", "") or getattr(
            getattr(self.offering, "model", None), "name", ""
        )
        return f"{provider_name}/{name}"


def _keys(provider: Any) -> list:
    """Credentials for *provider* from the prefetched relation (no query)."""
    return list(getattr(provider, "api_keys").all())


def _provider_ready(provider: Any) -> bool:
    """Whether the provider has any usable credential at all."""
    if provider is None or not getattr(provider, "enabled", True):
        return False
    if getattr(provider, "default_api_key", ""):
        return True
    return any(key.enabled for key in _keys(provider))


def _provider_can_pay(provider: Any) -> bool:
    """Whether the provider has a key that may call paid endpoints."""
    if provider is None:
        return False
    if getattr(provider, "default_api_key", ""):
        return True
    return any(key.enabled and (key.budget or 0) > 0 for key in _keys(provider))


def _effective_context(offering: Any) -> int:
    override = getattr(offering, "context_window_override", None)
    if override:
        return int(override)
    model = getattr(offering, "model", None)
    return int(getattr(model, "context_length", 0) or 0)


def _allowed_provider(offering: Any, constraints: dict[str, Any]) -> bool:
    provider = getattr(offering, "api_provider", None)
    if provider is None:
        return False
    allow = constraints.get("providers_allow") or []
    deny = constraints.get("providers_deny") or []
    identity = {str(provider.pk), provider.slug, provider.name}
    if allow:
        allow_ids = {str(value) for value in allow}
        if not identity.intersection(allow_ids):
            return False
    if deny:
        deny_ids = {str(value) for value in deny}
        if identity.intersection(deny_ids):
            return False
    return True


def _excluded_model(offering: Any, constraints: dict[str, Any]) -> bool:
    excluded = constraints.get("exclude_models") or []
    if not excluded:
        return False
    model = getattr(offering, "model", None)
    identity = {
        str(getattr(offering, "name", "") or ""),
        str(getattr(model, "name", "") or ""),
        str(getattr(model, "slug", "") or ""),
        str(getattr(model, "canonical_id", "") or ""),
    }
    return bool(identity.intersection(str(value) for value in excluded))


def matches(offering: Any, constraints: dict[str, Any]) -> bool:
    """Whether *offering* satisfies the hard constraints."""
    if not getattr(offering, "enabled", True):
        return False
    provider = getattr(offering, "api_provider", None)
    if not _provider_ready(provider):
        return False
    if _excluded_model(offering, constraints):
        return False
    if not _allowed_provider(offering, constraints):
        return False
    if constraints.get("free_only") and not getattr(offering, "is_free", False):
        return False
    if constraints.get("local_only") and getattr(offering, "is_cloud", True):
        return False
    if constraints.get("require_tools"):
        model = getattr(offering, "model", None)
        if not getattr(model, "supports_tool_call", False):
            return False
    min_context = constraints.get("min_context")
    if min_context:
        try:
            if _effective_context(offering) < int(min_context):
                return False
        except (TypeError, ValueError):
            pass
    min_tier = constraints.get("min_tier") or ""
    if min_tier:
        rank = getattr(offering, "leaderboard_rank", None)
        if not rank_satisfies(rank, min_tier):
            return False
    # A free-only key cannot call a paid offering.
    if not getattr(offering, "is_free", False) and not _provider_can_pay(provider):
        return False
    return True


def _load(offering: Any, cache: dict[int, int] | None = None) -> int:
    provider = getattr(offering, "api_provider", None)
    if provider is None:
        return 0
    pk = getattr(provider, "pk", None)
    if cache is not None and pk in cache:
        return cache[pk]
    try:
        value = int(provider.active_call_count()) + int(provider.requests_last_minute())
    except Exception:  # pylint: disable=broad-exception-caught
        value = 0
    if cache is not None and pk is not None:
        cache[pk] = value
    return value


def score(offering: Any, constraints: dict[str, Any], cache: dict[int, int] | None = None) -> float:
    """Higher is better.  Deterministic, cheap and easy to explain."""
    rank = getattr(offering, "leaderboard_rank", None)
    value = 400.0 if rank is None else max(0.0, 400.0 - float(rank))
    if constraints.get("prefer_free") and getattr(offering, "is_free", False):
        value += 120.0
    if constraints.get("prefer_low_load"):
        value -= 6.0 * min(_load(offering, cache), 25)
    else:
        value -= 2.0 * min(_load(offering, cache), 25)
    if getattr(offering, "health_blocks_calls", lambda: False)():
        value -= 5000.0
    provider = getattr(offering, "api_provider", None)
    status = str(getattr(provider, "status", "") or "")
    if status in ("DEGRADED", "RATE_LIMITED"):
        value -= 200.0
    elif status in ("UNAVAILABLE", "AUTH_ERROR", "CONFIG_ERROR"):
        value -= 2000.0
    return value


def _base_queryset(constraints: dict[str, Any] | None = None):
    """Enabled offerings with the cheap hard filters pushed into SQL."""
    from server.models.providers.ai_model_offering import AiModelOffering

    constraints = constraints or {}
    qs = (
        AiModelOffering.objects.filter(enabled=True, api_provider__enabled=True)
        .select_related("api_provider", "model")
        .prefetch_related("api_provider__api_keys")
    )
    if constraints.get("free_only"):
        qs = qs.filter(is_free=True)
    if constraints.get("local_only"):
        qs = qs.filter(is_cloud=False)
    if constraints.get("require_tools"):
        qs = qs.filter(model__supports_tool_call=True)
    max_rank = tier_max_rank(constraints.get("min_tier") or "")
    if max_rank is not None:
        qs = qs.filter(model__leaderboard_rank__lte=max_rank)
    min_context = constraints.get("min_context")
    if min_context:
        try:
            qs = qs.annotate(
                effective_context=Coalesce("context_window_override", "model__context_length")
            ).filter(effective_context__gte=int(min_context))
        except (TypeError, ValueError):
            pass
    allow = constraints.get("providers_allow") or []
    deny = constraints.get("providers_deny") or []
    if allow:
        allow_q = Q()
        for value in allow:
            if str(value).isdigit():
                allow_q |= Q(api_provider_id=int(value))
            else:
                allow_q |= Q(api_provider__slug=value) | Q(api_provider__name=value)
        qs = qs.filter(allow_q)
    if deny:
        for value in deny:
            if str(value).isdigit():
                qs = qs.exclude(api_provider_id=int(value))
            else:
                qs = qs.exclude(api_provider__slug=value).exclude(api_provider__name=value)
    excluded = constraints.get("exclude_models") or []
    if excluded:
        qs = qs.exclude(
            Q(name__in=excluded)
            | Q(model__name__in=excluded)
            | Q(model__slug__in=excluded)
            | Q(model__canonical_id__in=excluded)
        )
    return qs


def _offerings_for_name(name: str, constraints: dict[str, Any] | None = None) -> list[Any]:
    return list(_base_queryset(constraints).filter(Q(model__name=name) | Q(name=name)))


def _dedupe(candidates: Iterable[Candidate]) -> list[Candidate]:
    seen: set[tuple[int, int | None]] = set()
    out: list[Candidate] = []
    for candidate in candidates:
        pk = getattr(candidate.offering, "pk", None)
        key_pk = getattr(candidate.api_key, "pk", None)
        identity = (pk, key_pk)
        if pk is None or identity in seen:
            continue
        seen.add(identity)
        out.append(candidate)
        if len(out) >= MAX_CHAIN:
            break
    return out


def _current_offering(session: Any) -> Any:
    try:
        route = session.get_route()
    except Exception:  # pylint: disable=broad-exception-caught
        route = None
    offering = getattr(route, "offering", None) if route is not None else None
    if offering is not None and getattr(offering, "enabled", True):
        return offering
    return None


def _pinned_offering(intent: RouteIntent) -> Any:
    if not intent.pinned_offering_id:
        return None
    from server.models.providers.ai_model_offering import AiModelOffering

    return (
        AiModelOffering.objects.filter(pk=intent.pinned_offering_id)
        .select_related("api_provider", "model")
        .first()
    )


def _pinned_key(intent: RouteIntent) -> Any:
    if not intent.pinned_api_key_id:
        return None
    from server.models.providers.api_key import ApiKey

    return ApiKey.objects.filter(pk=intent.pinned_api_key_id).first()


def _ordered(offerings: Iterable[Any], constraints: dict[str, Any], current: Any) -> list[Any]:
    rows = list(offerings)
    cache: dict[int, int] = {}
    rows.sort(key=lambda offering: score(offering, constraints, cache), reverse=True)
    if current is not None:
        rows.sort(key=lambda offering: 0 if offering.pk == current.pk else 1)
    return rows


def build_chain(session: Any, intent: RouteIntent) -> list[Candidate]:
    """Return the ordered candidates the session may try."""
    constraints = dict(intent.constraints or {})
    current = _current_offering(session)

    # Strict pins ------------------------------------------------------
    if intent.pin == PIN_OFFERING_KEY:
        offering = _pinned_offering(intent)
        if offering is None:
            return []
        return [Candidate(offering, _pinned_key(intent), "pinned")]

    if intent.pin == PIN_OFFERING:
        offering = _pinned_offering(intent)
        if offering is None:
            return []
        chain = [Candidate(offering, _pinned_key(intent), "pinned provider")]
        if intent.allows_providers and offering.model is not None:
            for sibling in _ordered(
                [row for row in _offerings_for_name(offering.model.name, constraints)
                 if row.pk != offering.pk and matches(row, constraints)],
                constraints,
                current,
            ):
                chain.append(Candidate(sibling, None, "same model, other provider"))
        return _dedupe(chain)

    # Model pin --------------------------------------------------------
    if intent.pin == PIN_MODEL and intent.target:
        rows = [row for row in _offerings_for_name(intent.target, constraints) if matches(row, constraints)]
        if not rows:
            # The pinned name may be disabled/health-blocked — still offer the
            # exact row so the real error is visible instead of "no candidate".
            rows = [row for row in _offerings_for_name(intent.target) if getattr(row, "enabled", True)]
        chain = [
            Candidate(row, None, "pinned model")
            for row in _ordered(rows, constraints, current)
        ]
        if intent.allows_models:
            chain.extend(_model_fallback(constraints, current, exclude=intent.target))
        elif not rows:
            # Nothing serves the pinned name at all.  A model→model step is
            # the only way to keep the session useful; ordinary provider
            # failures still stay within the pinned model.
            chain.extend(_model_fallback(constraints, current, exclude=intent.target))
        return _dedupe(chain)

    # Auto / profile ---------------------------------------------------
    rows = [row for row in _base_queryset(constraints) if matches(row, constraints)]
    if not rows:
        # Relax only the soft-ish tier filter so an empty catalog still
        # produces a concrete, explainable failure instead of a blank chain.
        relaxed = {**constraints, "min_tier": "", "require_tools": False}
        rows = [row for row in _base_queryset(relaxed) if matches(row, relaxed)]
    chain = [
        Candidate(row, None, f"profile:{intent.profile or 'auto'}")
        for row in _ordered(rows, constraints, current)
    ]
    return _dedupe(chain)


def _model_fallback(
    constraints: dict[str, Any],
    current: Any,
    *,
    exclude: str,
) -> list[Candidate]:
    """Other models that satisfy the same constraints (model→model ladder)."""
    rows = []
    for offering in _base_queryset(constraints):
        if not matches(offering, constraints):
            continue
        name = getattr(getattr(offering, "model", None), "name", "") or offering.name
        if name == exclude:
            continue
        rows.append(offering)
    return [
        Candidate(row, None, "fallback model")
        for row in _ordered(rows, constraints, current)
    ]


def candidates_for_offering(offering: Any) -> list[Candidate]:
    """Convenience for callers that only have an offering (probes/tests)."""
    return [Candidate(offering, None, "explicit")]
