"""Autonomy policy for external agent CLIs run inside terminals.

External CLIs are ordinary terminal programs — there is no special tool
surface for them (``terminal_exec`` / ``terminal_send`` cover everything).
This module holds the one thing that *is* special: the autonomy policy
for recognized agent CLIs.

Two sets:

- ``EXTERNAL_CLI_ALLOWLIST`` — pre-approved binaries. Extend via
  ``config/settings_local.py``::

      TERMINAL_EXTERNAL_ALLOWLIST = ["my-tool"]

- ``KNOWN_AGENT_CLIS`` — recognition list of CLI-based agent systems.
  A *recognized but unapproved* agent CLI halts for approval
  (:func:`unapproved_agent_cli`), no matter which tool invoked it — the
  check lives in the terminal guardrail, so it cannot be bypassed by
  tool choice. Anything else (shell builtins, dev tools, unknown
  binaries) is covered by the normal content/path guardrails only.

Documented limitation: a brand-new agent CLI this list does not
recognize is treated as an ordinary program.
"""
from __future__ import annotations

import shlex

from django.conf import settings

#: Pre-approved binaries (agent CLIs plus common dev tools).
EXTERNAL_CLI_ALLOWLIST: tuple[str, ...] = (
    "claude",
    "hermes",
    "codex",
    "aider",
    "opencode",
    "gemini",
    "llm",
    "git",
    "gh",
    "npm",
    "npx",
    "yarn",
    "pnpm",
    "make",
    "pytest",
    "python3",
)

#: Recognized CLI-based agent systems (recognition, not permission).
KNOWN_AGENT_CLIS: frozenset[str] = frozenset({
    "claude",
    "hermes",
    "codex",
    "aider",
    "opencode",
    "gemini",
    "llm",
})


def allowed_binaries() -> set[str]:
    """Return the effective allowlist (stock + ``settings`` override)."""
    extra = getattr(settings, "TERMINAL_EXTERNAL_ALLOWLIST", None) or []
    return {*(b.lower() for b in EXTERNAL_CLI_ALLOWLIST), *(str(b).lower() for b in extra)}


def first_token(command: str) -> str:
    """Return the binary of a shell *command* (``"npx hermes …"`` → ``"npx"``)."""
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        parts = command.strip().split()
    if not parts:
        return ""
    token = parts[0]
    # ``VAR=x cmd`` env prefixes — skip them.
    idx = 0
    while idx < len(parts) and "=" in parts[idx] and not parts[idx].startswith("/"):
        idx += 1
    token = parts[idx] if idx < len(parts) else ""
    # Bare path → basename (``/usr/local/bin/claude`` → ``claude``).
    return token.rsplit("/", 1)[-1].lower()


def is_external_cli_allowed(cli: str) -> bool:
    """True when *cli* (binary or full command) is on the allowlist."""
    return first_token(cli) in allowed_binaries()


def unapproved_agent_cli(command: str) -> str:
    """Return the binary if *command* invokes an unapproved agent CLI.

    Returns ``""`` when the command invokes anything else (shell
    builtins, dev tools, unknown binaries — all covered by the normal
    content/path guardrails) or an allowlisted agent CLI.
    """
    binary = first_token(command or "")
    if not binary:
        return ""
    if binary in KNOWN_AGENT_CLIS and binary not in allowed_binaries():
        return binary
    return ""
