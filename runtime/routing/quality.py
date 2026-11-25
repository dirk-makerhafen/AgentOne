"""Human-readable quality tiers derived from the leaderboard rank.

The raw rank is useful for sorting but a terrible thing to ask a user to pick.
Tiers are stable buckets over the same number, so filters ("Strong or better")
and UI badges ("4 bars") are easy to explain and never drift from the ranking
data.
"""
from __future__ import annotations

#: (key, label, max_rank, bars).  ``None`` max_rank = catch-all bottom tier.
TIERS: tuple[tuple[str, str, int | None, int], ...] = (
    ("frontier", "Frontier", 20, 5),
    ("excellent", "Excellent", 60, 4),
    ("strong", "Strong", 150, 3),
    ("capable", "Capable", 350, 2),
    ("lightweight", "Lightweight", None, 1),
)

_TIER_INDEX = {key: index for index, (key, *_rest) in enumerate(TIERS)}
_TIER_MAX = {key: max_rank for key, _label, max_rank, _bars in TIERS}
_TIER_LABEL = {key: label for key, label, _max, _bars in TIERS}
_TIER_BARS = {key: bars for key, _label, _max, bars in TIERS}

#: Ordered from best to worst, for UI selects.
TIER_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (key, label) for key, label, _max, _bars in TIERS
)

#: "At least this good" filter options (empty = any).
QUALITY_FILTER_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "Any quality"),
    ("capable", "Capable or better"),
    ("strong", "Strong or better"),
    ("excellent", "Excellent or better"),
    ("frontier", "Frontier only"),
)


def tier_for_rank(rank: int | None) -> str:
    """Return the tier key for *rank* (``""`` when the rank is unknown)."""
    if rank is None:
        return ""
    for key, _label, max_rank, _bars in TIERS:
        if max_rank is not None and rank <= max_rank:
            return key
    return TIERS[-1][0]


def tier_label(tier: str) -> str:
    """Human label for a tier key."""
    return _TIER_LABEL.get(tier or "", "")


def tier_bars(tier: str) -> int:
    """0–5 bar indicator for a tier key."""
    return _TIER_BARS.get(tier or "", 0)


def tier_max_rank(tier: str) -> int | None:
    """Maximum leaderboard rank allowed by *tier*.

    Returns ``None`` for "no limit" (unknown tier / the lightweight catch-all).
    """
    return _TIER_MAX.get(tier or "")


def tier_index(tier: str) -> int:
    """Ordering index (lower is better); unknown tiers sort last."""
    return _TIER_INDEX.get(tier or "", len(TIERS))


def rank_satisfies(rank: int | None, min_tier: str) -> bool:
    """Whether *rank* meets the *min_tier* constraint.

    Unknown ranks are accepted for the broad tiers (capable/lightweight) but
    rejected for "strong or better": we should not silently route a user who
    asked for a strong model onto an unranked one.
    """
    if not min_tier:
        return True
    max_rank = tier_max_rank(min_tier)
    if max_rank is None:
        return True
    if rank is None:
        return min_tier in ("capable", "lightweight")
    return rank <= max_rank


def describe_rank(rank: int | None, is_estimate: bool = False) -> str:
    """Compact display string, e.g. ``"#42"`` / ``"~#120"`` / ``"—"``."""
    if rank is None:
        return "—"
    return f"{'~' if is_estimate else ''}#{rank}"
