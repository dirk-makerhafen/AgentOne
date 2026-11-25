"""Resolve a session's *route intent* from its immutable settings.

The intent answers three questions before any provider call:

* **What** is the session allowed to run on (a profile, a canonical model, an
  exact offering, or an exact offering + key)?
* **How much failover** is allowed when that target fails?
* **How long** may a call wait for the target before the router fails over?

The current binding (which provider/key actually served the last call) is not
part of the intent; it lives on :class:`~server.models.sessions.session_route.SessionRoute`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.routing.quality import TIER_CHOICES

# Pin levels ---------------------------------------------------------------
PIN_AUTO = "auto"
PIN_MODEL = "model"
PIN_OFFERING = "offering"
PIN_OFFERING_KEY = "offering_key"
PIN_CHOICES = (
    (PIN_AUTO, "Automatic"),
    (PIN_MODEL, "Model (any provider)"),
    (PIN_OFFERING, "Provider + model"),
    (PIN_OFFERING_KEY, "Provider + model + key (strict)"),
)

# Failover ladders ---------------------------------------------------------
FAILOVER_NONE = "none"
FAILOVER_KEYS = "keys"
FAILOVER_PROVIDERS = "providers"
FAILOVER_MODELS = "models"
FAILOVER_CHOICES = (
    (FAILOVER_NONE, "Never switch"),
    (FAILOVER_KEYS, "Rotate API keys"),
    (FAILOVER_PROVIDERS, "Switch provider (same model)"),
    (FAILOVER_MODELS, "Switch provider or model"),
)
_FAILOVER_ORDER = {
    FAILOVER_NONE: 0,
    FAILOVER_KEYS: 1,
    FAILOVER_PROVIDERS: 2,
    FAILOVER_MODELS: 3,
}

# Workloads ----------------------------------------------------------------
WORKLOAD_CHAT = "chat"
WORKLOAD_BACKGROUND = "background"
WORKLOAD_TEST = "test"

#: Default wait budgets (seconds) before failing over.  A user chatting should
#: not stare at a spinner; a background task can afford to wait for the right
#: model; a test must fail immediately with the real reason.
WORKLOAD_WAIT_SECONDS = {
    WORKLOAD_CHAT: 10,
    WORKLOAD_BACKGROUND: 120,
    WORKLOAD_TEST: 0,
}

# Named profiles -----------------------------------------------------------
#: ``prefer_free`` is a soft preference (score bonus), ``free_only`` a hard
#: filter.  ``min_tier`` maps to ``leaderboard_rank`` via
#: :mod:`runtime.routing.quality`.
PROFILES: dict[str, dict[str, Any]] = {
    "auto:balanced": {
        "label": "Balanced (free-first)",
        "description": "Strong or better, tools required, free routes preferred.",
        "constraints": {
            "prefer_free": True,
            "min_tier": "strong",
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": WORKLOAD_WAIT_SECONDS[WORKLOAD_CHAT],
    },
    "auto:best-free": {
        "label": "Best free",
        "description": "Only verified free routes; strong or better.",
        "constraints": {
            "free_only": True,
            "min_tier": "strong",
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": WORKLOAD_WAIT_SECONDS[WORKLOAD_CHAT],
    },
    "auto:best": {
        "label": "Best available",
        "description": "Excellent or better, paid routes allowed.",
        "constraints": {
            "prefer_free": False,
            "min_tier": "excellent",
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": WORKLOAD_WAIT_SECONDS[WORKLOAD_CHAT],
    },
    "auto:local": {
        "label": "Local only",
        "description": "Never leave this machine.",
        "constraints": {
            "local_only": True,
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": WORKLOAD_WAIT_SECONDS[WORKLOAD_CHAT],
    },
    "auto:fast": {
        "label": "Fast",
        "description": "Capable or better, least-loaded provider, short wait.",
        "constraints": {
            "prefer_free": True,
            "prefer_low_load": True,
            "min_tier": "capable",
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": 5,
    },
    "auto:reliable": {
        "label": "Reliable (background)",
        "description": "Strong or better; waits longer before switching.",
        "constraints": {
            "prefer_free": True,
            "min_tier": "strong",
            "require_tools": True,
        },
        "failover": FAILOVER_MODELS,
        "wait_seconds": WORKLOAD_WAIT_SECONDS[WORKLOAD_BACKGROUND],
    },
}

DEFAULT_PROFILE = "auto:balanced"

PROFILE_CHOICES = tuple(
    (name, spec["label"]) for name, spec in PROFILES.items()
)

#: Constraint keys understood by the candidate builder.
CONSTRAINT_KEYS = frozenset({
    "free_only",
    "local_only",
    "prefer_free",
    "prefer_low_load",
    "min_tier",
    "require_tools",
    "min_context",
    "providers_allow",
    "providers_deny",
    "exclude_models",
})


@dataclass(frozen=True)
class RouteIntent:
    """Resolved routing intent for one session."""

    pin: str = PIN_AUTO
    failover: str = FAILOVER_MODELS
    target: str = DEFAULT_PROFILE
    wait_seconds: int = WORKLOAD_WAIT_SECONDS[WORKLOAD_CHAT]
    constraints: dict[str, Any] = field(default_factory=dict)
    pinned_offering_id: int | None = None
    pinned_api_key_id: int | None = None
    profile: str = DEFAULT_PROFILE
    workload: str = WORKLOAD_CHAT

    # -- convenience -----------------------------------------------------
    @property
    def is_strict(self) -> bool:
        """True when the session must never move off its exact binding."""
        return self.pin == PIN_OFFERING_KEY or self.failover == FAILOVER_NONE

    @property
    def allows_keys(self) -> bool:
        return _FAILOVER_ORDER.get(self.failover, 0) >= _FAILOVER_ORDER[FAILOVER_KEYS]

    @property
    def allows_providers(self) -> bool:
        return _FAILOVER_ORDER.get(self.failover, 0) >= _FAILOVER_ORDER[FAILOVER_PROVIDERS]

    @property
    def allows_models(self) -> bool:
        return _FAILOVER_ORDER.get(self.failover, 0) >= _FAILOVER_ORDER[FAILOVER_MODELS]

    @property
    def label(self) -> str:
        if self.pin == PIN_OFFERING_KEY:
            return "Pinned (provider + model + key)"
        if self.pin == PIN_OFFERING:
            return f"Pinned provider · {self.target}"
        if self.pin == PIN_MODEL:
            return f"Model · {self.target}"
        return PROFILES.get(self.profile, {}).get("label", self.target or "Automatic")

    def with_workload(self, workload: str) -> "RouteIntent":
        """Return a copy with the workload's default wait budget applied."""
        if self.wait_seconds is not None:
            return self
        return RouteIntent(**{**self.__dict__, "wait_seconds": WORKLOAD_WAIT_SECONDS.get(workload, 10), "workload": workload})


def workload_for_session(session: Any) -> str:
    """Classify *session* as chat, background or test."""
    try:
        session_type = getattr(session.model, "session_type", "") or ""
    except Exception:  # pylint: disable=broad-exception-caught
        return WORKLOAD_CHAT
    if session_type == "test":
        return WORKLOAD_TEST
    if session_type == "session" and not getattr(session.model, "parent_session_id", None):
        return WORKLOAD_CHAT
    if session_type in ("", "session") and not getattr(session.model, "parent_session_id", None):
        return WORKLOAD_CHAT
    return WORKLOAD_BACKGROUND


def _setting(session: Any, name: str, default: Any = None) -> Any:
    try:
        return session._get_session_setting(name)  # pylint: disable=protected-access
    except Exception:  # pylint: disable=broad-exception-caught
        return default


def resolve_intent(session: Any, workload: str | None = None) -> RouteIntent:
    """Build the :class:`RouteIntent` for *session*.

    Reads the immutable settings only — never the current route binding — so
    the router can decide whether the existing binding is still acceptable.
    """
    workload = workload or workload_for_session(session)
    pinned_offering = _setting(session, "aimodel")
    pinned_key_id = None
    try:
        key = session.preferred_api_key()
        pinned_key_id = getattr(key, "pk", None)
    except Exception:  # pylint: disable=broad-exception-caught
        pinned_key_id = None

    explicit_pin = _setting(session, "route_pin") or ""
    explicit_target = (_setting(session, "route_target") or "").strip()
    explicit_failover = _setting(session, "route_failover") or ""
    explicit_wait = _setting(session, "route_wait_seconds")
    explicit_constraints = _setting(session, "route_constraints") or {}

    target = explicit_target
    if not target and pinned_offering is not None:
        try:
            target = pinned_offering.model.name
        except Exception:  # pylint: disable=broad-exception-caught
            target = pinned_offering.name or ""
    if not target:
        # No explicit target: honour the user's default automatic profile.
        try:
            from runtime.settings import get_default_route  # pylint: disable=import-outside-toplevel

            target = get_default_route()
        except Exception:  # pylint: disable=broad-exception-caught
            target = DEFAULT_PROFILE

    profile = target if target in PROFILES else DEFAULT_PROFILE

    # Pin inference ------------------------------------------------------
    if explicit_pin in {key for key, _ in PIN_CHOICES}:
        pin = explicit_pin
    elif target in PROFILES:
        pin = PIN_AUTO
    elif pinned_offering is not None:
        pin = PIN_MODEL
    else:
        pin = PIN_AUTO

    # A concrete pin is not a profile: the user picked a target, so profile
    # constraints (min tier, tools, ...) must not silently narrow it.
    if pin != PIN_AUTO:
        profile = ""

    if pin == PIN_AUTO and not target:
        target = profile or DEFAULT_PROFILE
    if pin in (PIN_OFFERING, PIN_OFFERING_KEY) and pinned_offering is None:
        # No concrete offering to pin: degrade to a model/auto target instead
        # of producing an empty chain.
        pin = PIN_MODEL if target and target not in PROFILES else PIN_AUTO

    # Failover inference -------------------------------------------------
    if explicit_failover in {key for key, _ in FAILOVER_CHOICES}:
        failover = explicit_failover
    elif pin == PIN_OFFERING_KEY:
        failover = FAILOVER_NONE
    elif pin == PIN_OFFERING:
        failover = FAILOVER_KEYS
    elif pin == PIN_MODEL:
        failover = FAILOVER_PROVIDERS
    else:
        failover = PROFILES.get(profile, {}).get("failover", FAILOVER_MODELS)
    if pin == PIN_OFFERING_KEY:
        failover = FAILOVER_NONE

    # Wait budget --------------------------------------------------------
    if explicit_wait is not None:
        try:
            wait_seconds = max(0, int(explicit_wait))
        except (TypeError, ValueError):
            wait_seconds = WORKLOAD_WAIT_SECONDS.get(workload, 10)
    elif pin == PIN_OFFERING_KEY:
        wait_seconds = 0
    elif pin == PIN_AUTO and profile in PROFILES:
        wait_seconds = int(PROFILES[profile].get("wait_seconds", WORKLOAD_WAIT_SECONDS.get(workload, 10)))
    else:
        wait_seconds = WORKLOAD_WAIT_SECONDS.get(workload, 10)

    # Constraints --------------------------------------------------------
    constraints: dict[str, Any] = {}
    if pin == PIN_AUTO and profile in PROFILES:
        constraints.update(PROFILES[profile].get("constraints") or {})
    if isinstance(explicit_constraints, dict):
        constraints.update(
            {key: value for key, value in explicit_constraints.items() if key in CONSTRAINT_KEYS}
        )
    constraints.setdefault("min_tier", "")

    return RouteIntent(
        pin=pin,
        failover=failover,
        target=target,
        wait_seconds=wait_seconds,
        constraints=constraints,
        pinned_offering_id=getattr(pinned_offering, "pk", None),
        pinned_api_key_id=pinned_key_id,
        profile=profile,
        workload=workload,
    )


def tier_choices() -> tuple[tuple[str, str], ...]:
    """Re-export for templates/forms that want the quality buckets."""
    return TIER_CHOICES
