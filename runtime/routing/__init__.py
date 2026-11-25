"""Routing: intent → candidate chain → admission → failover decisions.

Public surface used by ``call_llm`` and the session runtime:

* :func:`resolve_intent` — what the session is allowed to run on.
* :func:`build_chain` — the ordered ``(offering, key)`` candidates.
* :func:`decide_failure` / :func:`decide_admission` — wait vs fail over.
* :func:`get_route` / :func:`set_route` — the mutable current binding.
"""
from __future__ import annotations

from runtime.routing.candidates import Candidate, build_chain, matches, score
from runtime.routing.decisions import (
    ACTION_FAILOVER,
    ACTION_RAISE,
    ACTION_WAIT,
    ErrorDecision,
    decide_admission,
    decide_failure,
)
from runtime.routing.intent import (
    DEFAULT_PROFILE,
    FAILOVER_CHOICES,
    FAILOVER_KEYS,
    FAILOVER_MODELS,
    FAILOVER_NONE,
    FAILOVER_PROVIDERS,
    PIN_AUTO,
    PIN_CHOICES,
    PIN_MODEL,
    PIN_OFFERING,
    PIN_OFFERING_KEY,
    PROFILE_CHOICES,
    PROFILES,
    WORKLOAD_BACKGROUND,
    WORKLOAD_CHAT,
    WORKLOAD_TEST,
    WORKLOAD_WAIT_SECONDS,
    RouteIntent,
    resolve_intent,
    workload_for_session,
)
from runtime.routing.quality import (
    QUALITY_FILTER_CHOICES,
    TIER_CHOICES,
    describe_rank,
    rank_satisfies,
    tier_bars,
    tier_for_rank,
    tier_label,
    tier_max_rank,
)
from runtime.routing.state import (
    clear_route,
    get_route,
    record_attempt,
    set_route,
)

__all__ = [
    "ACTION_FAILOVER",
    "ACTION_RAISE",
    "ACTION_WAIT",
    "Candidate",
    "DEFAULT_PROFILE",
    "ErrorDecision",
    "FAILOVER_CHOICES",
    "FAILOVER_KEYS",
    "FAILOVER_MODELS",
    "FAILOVER_NONE",
    "FAILOVER_PROVIDERS",
    "PIN_AUTO",
    "PIN_CHOICES",
    "PIN_MODEL",
    "PIN_OFFERING",
    "PIN_OFFERING_KEY",
    "PROFILES",
    "PROFILE_CHOICES",
    "QUALITY_FILTER_CHOICES",
    "RouteIntent",
    "TIER_CHOICES",
    "WORKLOAD_BACKGROUND",
    "WORKLOAD_CHAT",
    "WORKLOAD_TEST",
    "WORKLOAD_WAIT_SECONDS",
    "build_chain",
    "clear_route",
    "decide_admission",
    "decide_failure",
    "describe_rank",
    "get_route",
    "matches",
    "rank_satisfies",
    "record_attempt",
    "resolve_intent",
    "score",
    "set_route",
    "tier_bars",
    "tier_for_rank",
    "tier_label",
    "tier_max_rank",
    "workload_for_session",
]
