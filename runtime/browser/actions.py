"""Action catalogue shared by the tool and the approval gate.

``READ_ONLY_ACTIONS`` inspect the page; they never change remote state and
never write to disk, so they run without approval.  ``MUTATING_ACTIONS``
navigate, submit, or move data across the trust boundary (including
``evaluate``, which can do anything the page can), so they park at
``HALTED_APPROVAL`` for a human to accept.  ``wait``/``close_tab`` are neutral
housekeeping that cannot change server state.
"""

from __future__ import annotations

READ_ONLY_ACTIONS = frozenset({"status", "snapshot", "read", "tabs", "cookies", "wait", "close_tab"})
MUTATING_ACTIONS = frozenset({"open", "navigate", "click", "type", "back", "evaluate", "upload", "download"})

ALL_ACTIONS = READ_ONLY_ACTIONS | MUTATING_ACTIONS


def is_known(action: str) -> bool:
    return action in ALL_ACTIONS


def requires_approval(action: str) -> bool:
    return action in MUTATING_ACTIONS
