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

from server.models.providers.ai_model_offering import AiModelOffering as AiModel


class ModelGroup:
    """A canonical model name with its usable per-provider ``AiModel`` rows.

    Instances are the subjects of the composer dropdown's group options
    (weakref-able, unlike a bare dict)."""

    # pylint: disable=too-few-public-methods
    __slots__ = (
        "name",
        "members",
        "provider_count",
        "is_favorite",
        "is_free",
        "rank",
        "tier",
        "bars",
        "__weakref__",
    )

    def __init__(self, name: str, members: List[AiModel]) -> None:
        from runtime.routing.quality import tier_bars, tier_for_rank

        self.name = name
        self.members = members
        self.provider_count = len({m.api_provider_id for m in members})
        raw = getattr(members[0], "model", None) if members else None
        self.is_favorite = bool(getattr(raw, "is_favorite", False))
        self.is_free = any(bool(m.is_free) for m in members)
        ranks = [m.leaderboard_rank for m in members if m.leaderboard_rank is not None]
        self.rank = min(ranks) if ranks else None
        self.tier = tier_for_rank(self.rank)
        self.bars = tier_bars(self.tier)

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
            | Q(api_provider__default_api_key__gt="")
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


def selectable_aimodels() -> List[AiModel]:
    """Return usable rows that are not currently health-blocked.

    ``available_aimodels`` answers "is this row configured?"; this adds the
    observed-health filter used by the picker and fallback path.  Sticky
    failures (``UNAVAILABLE`` / ``AUTH_ERROR``) stay out until a probe or a
    successful call clears them; ``DEGRADED`` rows return after their backoff.
    """
    return [model for model in available_aimodels() if not model.health_blocks_calls()]


def model_groups(
    *,
    favorites_only: bool = False,
    free_only: bool = False,
    local_only: bool = False,
    min_tier: str = "",
    search: str = "",
) -> ModelGroupList:
    """Return model groups ordered by name, optionally filtered.

    A group carries every ENABLED provider row serving the canonical name —
    including providers without an API key yet or with an observed health
    problem (the dropdown renders those dimmed).  Only names with at least one
    selectable member are offered, so clicking a group always resolves to a
    concrete row.

    Filters are applied at the *group* level: a model qualifies when at least
    one of its provider rows satisfies the filter, so "free" does not hide a
    name that also has a paid route.
    """
    from runtime.routing.quality import rank_satisfies

    usable_names = {m.name for m in selectable_aimodels()}
    needle = (search or "").strip().lower()
    by_name: Dict[str, List[AiModel]] = {}
    for model in AiModel.objects.filter(enabled=True).select_related("model", "api_provider"):
        members = by_name.setdefault(model.name, [])
        if model.api_provider_id not in {m.api_provider_id for m in members}:
            members.append(model)

    def qualifies(name: str, members: List[AiModel]) -> bool:
        if name not in usable_names:
            return False
        if needle and needle not in name.lower() and needle not in (
            getattr(members[0], "developer", "") or ""
        ).lower():
            return False
        if favorites_only and not any(
            bool(getattr(m.model, "is_favorite", False)) for m in members
        ):
            return False
        if free_only and not any(bool(m.is_free) for m in members):
            return False
        if local_only and not any(not bool(m.is_cloud) for m in members):
            return False
        if min_tier and not any(
            rank_satisfies(m.leaderboard_rank, min_tier) for m in members
        ):
            return False
        return True

    groups = [
        ModelGroup(name, members)
        for name, members in sorted(by_name.items())
        if qualifies(name, members)
    ]
    # Favourites float to the top of every list; the rest stay alphabetical.
    groups.sort(key=lambda group: (not group.is_favorite, group.name.lower()))
    return ModelGroupList(groups)


def sibling_aimodels(model: AiModel, *, exclude: List[int] | None = None) -> List[AiModel]:
    """Return the other usable rows serving the same canonical name as *model*,
    ordered by ascending live load (least-loaded first).

    ``exclude`` may carry pks of rows already tried so a failed sibling is not
    retried in the same fallback pass.
    """
    exclude_pks = {int(pk) for pk in (exclude or ())}
    exclude_pks.add(model.pk)
    members = [m for m in selectable_aimodels() if m.name == model.name and m.pk not in exclude_pks]
    return sorted(members, key=_member_load)


def pick_aimodel(name: str, *, stable: bool = False) -> AiModel | None:
    """Return a concrete :class:`AiModel` for the canonical model *name*.

    1. Gather usable rows for the name that are not health-blocked.
    2. Exclude members whose provider is currently at/over its live free-tier
       rate caps (provider fields only — models themselves stay unlimited by
       default).
    3. Weighted-random selection toward the least-loaded remaining member, so
       the choice is not fully deterministic.
    4. If every member is throttled, fall back to any healthy member (the rate
       limiter will park the call rather than hard-fail).  Rows blocked by an
       observed failure are never returned.

    ``stable=True`` skips the random weighting and picks the least-loaded
    member deterministically (ties broken by pk).  Used for implicit default
    resolution, where a property read must not flap between providers.
    """
    members = [m for m in selectable_aimodels() if m.name == name]
    if not members:
        return None
    unthrottled = [m for m in members if not _provider_is_throttled(m)]
    candidates = unthrottled or members
    if stable:
        return sorted(candidates, key=lambda m: (_member_load(m), m.pk))[0]
    weights = [1.0 / (1.0 + _member_load(m)) for m in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _member_load(model: AiModel) -> int:
    """Coarse live load score for the provider serving *model*.

    Based on successful requests in the last minute plus currently active runs.
    """
    provider = model.api_provider
    return provider.active_call_count() + provider.requests_last_minute()


def _provider_is_throttled(model: AiModel) -> bool:
    """True when the provider serving *model* is at/over a live rate cap.

    Delegates to :meth:`ApiProvider.is_rate_limited`, which covers the
    parallel-call limit plus all request/token windows.
    """
    return model.api_provider.is_rate_limited()[0]
