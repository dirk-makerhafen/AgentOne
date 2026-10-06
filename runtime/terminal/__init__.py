"""Agent-only persistent terminal backend (libtmux wrapper)."""
from runtime.terminal.allowlist import (
    EXTERNAL_CLI_ALLOWLIST,
    KNOWN_AGENT_CLIS,
    is_external_cli_allowed,
    unapproved_agent_cli,
)
from runtime.terminal.manager import (
    cleanup_orphans,
    ensure_terminal,
    exec_command,
    kill_terminal,
    list_terminals,
    poll_output,
    reap_idle_terminals,
    send_input,
    tmux_available,
)

__all__ = [
    "EXTERNAL_CLI_ALLOWLIST",
    "KNOWN_AGENT_CLIS",
    "cleanup_orphans",
    "ensure_terminal",
    "exec_command",
    "is_external_cli_allowed",
    "kill_terminal",
    "list_terminals",
    "poll_output",
    "reap_idle_terminals",
    "send_input",
    "tmux_available",
    "unapproved_agent_cli",
]
