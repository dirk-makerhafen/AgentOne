# Session Hooks — per-call intercepts

**Status:** implemented — loader, runtime, scheduler wiring, tests
(`server/tests/test_intercept_hooks.py`, `server/tests/test_session_end.py`).
No UI.

Hooks are **per-call intercepts**: a `before:`/`after:` entry on the session
agent fires around every matching tool/task/command call. There are no bespoke
lifecycle events any more — the moments that used to be events are ordinary
tasks, so they are hooked like anything else:

| Old event | Replacement |
|---|---|
| `session_end` | the `session_end` task (`.agentone/scripts/core/session_end.py`), matched with `match: {name: session_end}` |
| `pre_compact` / `post_compact` | `before:` / `after:` on the `compact_turn` chain |
| `stop` | removed (no equivalent task; add an `after:` on `decide_next_step` / `process_turn` if needed) |

This keeps one mechanism and one contract: **`before` receives the call's
original kwargs and returns kwargs; `after` receives the call's result and
returns a result** (pass-through to leave it unmodified).

---

## 1. Manifest shape

```yaml
# agent.md
hooks:
  - name: reflect-on-session-end      # free label (matches on the intercepted call, not this)
    match:                            # optional filter — omitted dimensions are wildcards
      name: session_end
      session_type: "session | subsession | subtask_delegate | subtask_fork"
    after: reflect_session            # task of the SAME agent
    # mode defaults to detached for after: (inline blocks the parent)
```

Entry keys: `name` (optional label), `match` (optional filter), exactly one of
`before` / `after` (the same-agent task name), `mode`, `on_error`.
`blocking: true` is rejected (deferred sync tier — see §6).

### `match` filters

| Key | Compares against | Notes |
|---|---|---|
| `name` | the intercepted call's definition name | glob, `|`/`,`-separated alternatives; shorthand `match: "write*"` |
| `type` | the call's `TaskType` | case-insensitive: `tool`, `task`, `command`, `webapi`, `webview` |
| `session` | the session name | glob |
| `session_type` | the session's `SessionType` | case-insensitive glob: `session`, `subsession`, `subtask_delegate`, `subtask_fork`, `subtask_compaction`, `subtask_hook` |

All declared dimensions must match (AND); omitted dimensions are wildcards.

## 2. Modes and failure policy

- `mode: inline` — the hook is part of the call's before/after chain. A
  `before` transform blocks the call (the call waits on the hook via arg
  references); an `after` transform makes the parent wait via
  `WAITING_SUBTASKS_OR_HOOKS`.
- `mode: detached` — fire-and-forget; the return value is ignored and the
  parent never waits. Detached `before` hooks get a **snapshot** of the
  original arguments.
- Defaults: `before` → `inline`, `after` → `detached`.
- `on_error`: `fail_closed` (block/cancel the parent) or `fail_open` (let it
  proceed). Defaults follow the mode (`fail_closed` for inline,
  `fail_open` for detached). Inline `before` is always `fail_closed` — a
  failed input transform has no sound fallback.

## 3. Contract details

- **`before`** is dispatched with the original kwargs; its return value
  becomes the intercepted call's kwargs (chain in declaration order).
- **`after`** is dispatched with the intercepted call's result — returned by
  the last step for a chain (`compact_turn` yields
  `ingest_compaction`'s result) — resolved through the normal
  call-reference/auto-await machinery, so a `Message`/`AgentTaskCall`
  reference in the result arrives as a model instance.
- Hook tasks run **as the same agent, in the intercepted call's own session**
  (resolved by task name). There is deliberately no cross-agent dimension.

## 4. Scope and recursion

- `SUBTASK_HOOK` and `SUBTASK_COMPACT` worker sessions never fire intercepts.
- A hook task's own calls never refire intercepts (the recursion guard).
- `TaskInstance`s are per `(task, session, session_version)`, so concurrent
  sessions of one agent each get their own hook executions.
- Entries merge through `extends`, keyed on `name`.

## 5. The `session_end` task

Deactivation is a single path: `Session.request_end(reason=...)` dispatches
the `session_end` task (registered in `.agentone/scripts/core/scripts.md`,
core-group so every agent inherits it). `Session.set_is_active` is now a
low-level setter that fires no hooks; `request_end` falls back to a direct
write if the task is unavailable, so a missing script can never leave a
session active.

The task flips `is_active` to `False` and returns
`{reason, session_type, last_message_pk, transitioned}` — the frame an
`after:` hook forks from (anchor on `last_message_pk`, never the moving tail).

The worker session types (`subtask_hook`, `subtask_compaction`) never fire
intercepts (§4), and a hook can scope further on `match.session_type` — e.g.
the reflection mixin runs only for `session` / `subsession` /
`subtask_delegate` / `subtask_fork`, so it never reflects on a compaction or
hook worker.

Callers: `decide_next_step` (allowlist violation, and single-use subtask
completion with `reason="final_result"`) and `ingest_compaction`
(`reason="compaction_done"` on the compaction child).

## 6. Non-goals

V1 hooks cannot gate/veto with millisecond budgets or inject into a live turn
beyond the inline transform/failure contract. `blocking: true` is rejected at
load with a clear error so the sync tier can be added without a config
migration. No cadence triggers and no hook-chaining (see §4).

---

**See also:** [Manifest format](manifest-format.md) · [Architecture](architecture.md) · [Core mechanisms](core-mechanisms.md)
