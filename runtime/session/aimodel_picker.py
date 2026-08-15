"""Helpers for choosing an :class:`AiModel` — used by the composer model
dropdown and the default-model fallback.

A model is identified by its canonical display ``name`` (the models.yaml
catalog label).  Several providers may serve the same name; each is a separate
``AiModel`` row pinned to its own provider (and its provider-side KV cache).
These helpers group the usable rows by name and pick one concrete
(provider, model) row — preferring members that are usable and not currently
throttled, then random (weighted toward the least-loaded).
"""
from __future__ import annotations

import random
from typing import Dict, List

from django.db.models import Q

from server.models.providers.ai_model import AiModel


class ModelGroup:
    """A canonical model name with its usable per-provider ``AiModel`` rows.

    Instances are the subjects of the composer dropdown's group options
    (weakref-able, unlike a bare dict)."""

    # pylint: disable=too-few-public-methods
    __slots__ = ("name", "members", "provider_count", "__weakref__")

    def __init__(self, name: str, members: List[AiModel]) -> None:
        self.name = name
        self.members = members
        self.provider_count = len({m.api_provider_id for m in members})

    def __repr__(self) -> str:
        return f"<ModelGroup {self.name!r} ({self.provider_count} providers)>"


class ModelGroupList(list):
    """Ordered group list that UI views can weak-reference (plain lists can't)."""


def available_aimodels() -> List[AiModel]:
    """Return usable model rows — enabled, served by a provider that either
    has an enabled API key or a ``default_api_key`` — deduplicated to one row
    per (provider, name)."""
    rows = list(
        AiModel.objects.filter(enabled=True)
        .filter(
            Q(api_provider__api_keys__enabled=True)
            | Q(api_provider__raw_data__contains='"default_api_key"')
        )
        .distinct()
    )
    seen = set()
    result: List[AiModel] = []
    for model in rows:
        key = (model.api_provider_id, model.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(model)
    return result


def model_groups() -> ModelGroupList:
    """Return usable model groups ordered by name.

    A group carries every ENABLED provider row serving the canonical name,
    excluding providers without a configured API key yet.  Only
    names with at least one usable member are offered, so clicking a group
    always resolves to a concrete row.
    """
    usable_names = {m.name for m in available_aimodels()}
    by_name: Dict[str, List[AiModel]] = {}
    for model in AiModel.objects.filter(enabled=True):
        if model.api_provider.api_keys.count() == 0:
            continue
        members = by_name.setdefault(model.name, [])
        if model.api_provider_id not in {m.api_provider_id for m in members}:
            members.append(model)
    return ModelGroupList(
        ModelGroup(name, members)
        for name, members in sorted(by_name.items())
        if name in usable_names
    )


def sibling_aimodels(model: AiModel, *, exclude: List[int] | None = None) -> List[AiModel]:
    """Return the other usable rows serving the same canonical name as *model*,
    ordered by ascending live load (least-loaded first).

    ``exclude`` may carry pks of rows already tried so a failed sibling is not
    retried in the same fallback pass.
    """
    exclude_pks = {int(pk) for pk in (exclude or ())}
    exclude_pks.add(model.pk)
    members = [m for m in available_aimodels() if m.name == model.name and m.pk not in exclude_pks]
    return sorted(members, key=_member_load)


def pick_aimodel(name: str) -> AiModel | None:
    """Return a concrete :class:`AiModel` for the canonical model *name*.

    1. Gather usable rows for the name.
    2. Exclude members whose provider is currently at/over its live free-tier
       rate caps (provider fields only — models themselves stay unlimited by
       default).
    3. Weighted-random selection toward the least-loaded remaining member, so
       the choice is not fully deterministic.
    4. If every member is throttled, fall back to any member (the rate limiter
       will park the call rather than hard-fail).
    """
    members = [m for m in available_aimodels() if m.name == name]
    if not members:
        return None
    unthrottled = [m for m in members if not _provider_is_throttled(m)]
    candidates = unthrottled or members
    weights = [1.0 / (1.0 + _member_load(m)) for m in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _member_load(model: AiModel) -> int:
    """Coarse live load score for the provider serving *model*.

    Based on successful requests in the last minute.  (The ``active_call_count``
    helpers on the providers are currently non-functional, so parallelism is not
    included in the score.)
    """
    return model.api_provider.requests_last_minute()


def _provider_is_throttled(model: AiModel) -> bool:
    """True when the provider serving *model* is at/over a live rate cap.

    Mirrors the provider tier of :meth:`ApiProvider.is_rate_limited` using the
    configured limit fields and live usage windows.  Parallel-call checks are
    skipped — ``ApiProvider.active_call_count()`` is not functional yet.
    """
    # pylint: disable=too-many-return-statements
    provider = model.api_provider
    if provider.limit_request_per_minute > 0 and provider.requests_last_minute() >= provider.limit_request_per_minute:
        return True
    if provider.limit_request_per_hour > 0 and provider.requests_last_hour() >= provider.limit_request_per_hour:
        return True
    if provider.limit_request_per_day > 0 and provider.requests_today() >= provider.limit_request_per_day:
        return True
    if provider.limit_tokens_per_minute > 0 and provider.tokens_last_minute() >= provider.limit_tokens_per_minute:
        return True
    if provider.limit_tokens_per_hour > 0 and provider.tokens_last_hour() >= provider.limit_tokens_per_hour:
        return True
    if provider.limit_tokens_per_day > 0 and provider.tokens_today() >= provider.limit_tokens_per_day:
        return True
    return False
