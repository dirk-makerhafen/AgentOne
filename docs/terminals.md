# Persistent terminals & external agents

Agent sessions can keep **named persistent shells** that survive individual
tool calls — unlike the one-shot `shell` tool, which runs a command and
exits. Terminals back long-running commands, interactive CLIs, development
workflows (`npm run dev`, `pytest -f`), background jobs, and CLI-based
external agent systems such as **Claude Code** or **Hermes**.

Terminals are **agent-only**: the agent drives them through tools; the
browser UI shows a read-only viewer (session right panel → Terminals tab)
with refresh and kill actions, but no input.

## Concepts

| Concept | Meaning |
|---|---|
| Named terminal | One persistent shell per `(session, name)` pair, e.g. `default`, `dev`, `agent`. Names isolate workflows. |
| `TerminalSession` | Bookkeeping row (`server/models/terminal.py`): tmux name, status (`created`/`running`/`dead`), cwd, log path. Unique per `(session, name)`. |
| tmux backend | Each row maps 1:1 to a tmux session `agentone-s<sid>-<name>` via **libtmux**. The PTY survives worker restarts; the row lets the server reattach, list, and reap it. |
| External CLI | A CLI-based agent/tool (`claude`, `hermes`, …) executed *inside* a terminal. |

## Tools (`execution` group)

| Tool | Purpose |
|---|---|
| `terminal_exec(command, terminal="default", timeout=60)` | Run a command in the named terminal and wait for exit (sentinel-marker based, up to 600s). Creates the terminal on first use in the session workspace. |
| `terminal_send(text, terminal="default", submit=True)` | Send keystrokes — drive interactive prompts, answer an external agent's questions. |
| `terminal_poll(terminal="default", lines=200)` | Read the visible buffer without executing anything. Poll long jobs or interactive output. |
| `terminal_list()` | List this session's terminals with liveness info. |
| `terminal_kill(terminal="default")` | Destroy a terminal (tmux session + row marked `dead`). |

There is deliberately no special tool surface for external agents — they
are ordinary terminal programs. Typical interactive flow:

```
terminal_exec("claude -p 'summarize this repo'", terminal="agent")
terminal_poll(terminal="agent")             # read long output
terminal_send("…answer…", terminal="agent") # respond to a prompt
terminal_kill(terminal="agent")             # clean up
```

## External agent CLIs (recognition + ask)

External CLIs run through the same `terminal_*` tools as everything else.
The one thing that *is* special is the autonomy policy in
`runtime/terminal/allowlist.py`: a **recognition list** of known agent CLIs
(`KNOWN_AGENT_CLIS`: `claude`, `hermes`, `codex`, `aider`, `opencode`,
`gemini`, `llm`) plus an **allowlist** of pre-approved binaries (those plus
`git`, `gh`, `npm`, `npx`, `yarn`, `pnpm`, `make`, `pytest`, `python3`).
Extend in `config/settings_local.py`:

```python
TERMINAL_EXTERNAL_ALLOWLIST = ["my-tool"]
```

A *recognized but unapproved* agent CLI does **not** run silently — the
terminal scheduler guardrail parks the call at `HALTED_APPROVAL` so a human
decides. The check lives on `terminal_exec`/`terminal_send` themselves, so
it cannot be bypassed by tool choice. Everything else (shell builtins, dev
tools, unknown binaries) is covered by the normal content/path guardrails
only, keeping everyday shell use noise-free. Documented limitation: a
brand-new agent CLI the recognition list does not know is treated as an
ordinary program.

## Guardrails

Three layers, mirroring `shell`/`python`:

1. **Scheduling** — `terminal_exec`/`terminal_send` run the sh-guard +
   workspace path checks plus the agent-CLI recognition gate;
   `terminal_*` carry `access: read/write` postures in `scripts.md`,
   so out-of-policy paths trigger approval.
2. **Tool level** — each tool re-checks content (score ≥ 90) and path `deny`
   before touching tmux.
3. **Execution** — `BoundTask._filesystem_access_block` hard-blocks path
   `deny` verdicts (no approval override).

`AUTO_REVIEW_TOOL_NAMES` includes the new tools, so halted calls also go
through the `approval_decider` review.

## Lifecycle & settings

- Created lazily on first tool use; `ensure` is idempotent (one tmux session
  per row, repaired if missing). A tmux session that vanished (externally
  killed, reboot) is recreated transparently on the next tool call.
- Commands that end their own shell (`exit`, `exec`, killing their own PID)
  close the terminal: the call fails fast with `shell_exited: true` instead
  of polling until timeout, and the next call gets a fresh terminal.
- Idle reaping: the 10s `tick_scheduler` kills terminals idle longer than
  `TERMINAL_IDLE_TTL_SECONDS` (default 3600; 0 disables).
- Startup: `startup_cleanup` kills tmux sessions with no live row and marks
  rows whose tmux session vanished as `dead`.
- `server setup` reports whether the `tmux` binary + `libtmux` are present.
  Both are required for live use; without them tools return a clear error.

```python
# config/settings_local.py
TERMINAL_ENABLED = True
TERMINAL_IDLE_TTL_SECONDS = 3600
TERMINAL_MAX_OUTPUT_CHARS = 20000
TERMINAL_EXTERNAL_ALLOWLIST = []
```

## UI viewer

Session right panel → **Terminals** tab (`RightPanelSessionTerminals`):
lists each terminal (name, status, tmux liveness, cwd, last activity),
shows the tail of its `pipe-pane` log on selection, and offers Refresh and
Kill. No input — control stays with the agent. The log is the raw pty
stream, so the viewer (like the tool results) strips ANSI sequences,
bracketed-paste toggles, backspace overstrikes, and `\r` redraws via
`clean_terminal_output` before display.

## Tests

- `server/tests/test_terminal.py` — allowlist, slug/naming, manager
  (ensure idempotency, sentinel exec, kill, idle reap) with a fake tmux
  server; no `tmux` binary required.
- `.agentone/scripts/execution/test_terminal.py` — tool delegation with
  a mocked manager.
- `server/tests/test_terminal_ui.py` — right-panel tab rows/selection/kill
  with a mocked manager.

---

**See also:** [User guide](user-guide.md) (Terminals section) · [Models](models.md) (`TerminalSession`) · [Manifest format](manifest-format.md) (`access:` posture) · [Deployment](deployment.md) (tmux prerequisite)
