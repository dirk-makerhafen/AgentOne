# Session Hooks — detached agent work at lifecycle points

**Status:** implemented (increment 1) — model, loader, runtime, four
dispatch points, tick reaper, tests (``server/tests/test_hooks.py``,
``server/tests/test_hooks_loader.py``). No UI. No synchronous/control hooks.
**Scope:** v1 — async agent-fork hooks on four session lifecycle events, with
matchers, token budgets and timeouts. No UI. No synchronous/control hooks
(see §11 for the deliberately deferred sync tier).

---

## 1. Problem

Agents need to do work *around* the conversation without doing it *in* the
conversation: distill memory after a turn, archive a transcript before it is
compacted away, write a journal when a session ends, notify an external
system when a subagent finishes. Today each of these is bespoke plumbing
(compaction fork, todo auto-processing, cron) or impossible.

What we want is one mechanism: **when lifecycle event X fires in a session,
run task T with the session's context, detached, without making the session
wait** — and let T decide what happens (write a file, update a collection,
call an API, nothing at all). No sinks are built into the framework; the
called task owns its effects.

## 2. Industry alignment

Claude Code, OpenCode (SST) and Hermes (NousResearch) converged on the same
model — **event → matcher → handler** — at three cadences (Claude's framing):
per-session (start/end), per-turn (prompt-submit/stop), per-tool-call
(pre/post). Our events map 1:1 onto theirs:

| This doc | Claude Code | OpenCode | Hermes |
|---|---|---|---|
| `stop` (§5.1) | `Stop` / `SubagentStop` (auto-converted in subagents; blockable, `additionalContext`) | — | `post_llm_call`, `pre_verify` (keep-going gate) |
| `pre_compact` / `post_compact` (§5.2) | `PreCompact` (blockable; documented use: *archive full transcript*) + `PostCompact`, matchers `manual`/`auto`; `SessionStart`+`compact` to re-inject context | `experimental.session.compacting`; compaction hook can supply the summary | `session:compress` (observer: old/new id, `in_place`) |
| `session_end` (§5.3) | `SessionEnd` (matchers `clear`/`resume`/`logout`/`other`; shared 1.5s budget) | `session.*` via event bus | `session:end`, `on_session_end`, `on_session_finalize` |

Two findings shape this design:

- **Memory-around-compaction is the canonical hooks use case everywhere.**
  Claude documents transcript archival (`PreCompact`) and context re-injection
  after compaction as headline patterns. We are standardising existing
  practice, not inventing.
- **Everyone splits sync/control from async/observer.** Claude has
  `async: true` / `asyncRewake`; Hermes has outbound webhooks and
  drop-oldest observer queues; OpenCode has the event bus. Blocking hooks get
  10s–600s timeouts and fail-open semantics; observers never park the agent.
  **V1 is the async tier only** (§11 names the deferred sync tier so the
  manifest shape does not preclude it).

Where we deliberately diverge: **what a handler is.** Claude runs shell/HTTP/
MCP/prompt/judge-subagent handlers; Hermes runs in-process Python, plugin
callbacks, shell scripts, or webhooks; OpenCode runs in-process TS callbacks.
None run a hook as a **full agent fork with its own turn loop**. Ours does —
a superset in power (multi-turn agentic work with tools) and the only
substrate fitting "the called task decides what happens."

One enabling difference: Claude budgets `SessionEnd` at 1.5s because the
process is going away. Our sessions are DB rows, so a `session_end` fork
running minutes after deactivation is sound. State this in code comments
wherever the reaper or dispatcher could tempt a "fix."

## 3. Concepts

```
event  →  matcher  →  handler  →  detached fork run (with budget + deadline)
```

- **Event** (§5): a lifecycle point with a single choke-point dispatcher.
  V1: `stop`, `pre_compact`, `post_compact`, `session_end` — plus per-call
  intercept entries (§5.4), which have no `on:` (`before` *is* pre,
  `after` *is* post).
- **Matcher** (§6): a cheap string/regex filter evaluated at dispatch
  (session type, compaction trigger, end reason). Turns hardcoded gates into
  user configuration. Every event supports matchers, as in all three
  reference systems.
- **Handler** (§7): v1 is always an **agent fork** running a configured
  task/chain (`agent` + `task`). Phase 2 adds `command:` handlers reusing
  the scripts.md `SCRIPT` execution mode for trivial-cost hooks
  (log lines, `curl` notifications) without an LLM round-trip.
- **Run** (§9): a `SessionHookRun` row tracking the dispatch, its root call
  and its deadline — the unit the timeout reaper operates on.

Non-principles: no result sinks in the framework (the task owns effects);
no polling/cadence triggers (all v1 events are fired at their choke point,
not discovered by a tick scan); the parent never waits (no auto-await into
the parent — §8).

## 4. Why fork-only (no `mode: fork | insession`)

Considered and rejected for v1. Running a hook as a turn *in* the parent
session drags in the whole turn machinery: hook messages pollute the chain
(visible in chat, burned into every future context), trip
`decide_next_step` heuristics and turn counters, hold the session queue
strategy (the parent reads as *busy* — the waiting this feature exists to
avoid), and subject hook tool calls to guardrails (a detached reflection
calling `edit` could park an approval card in the user's chat). It would also
need hidden-message plumbing plus UI filtering — real bug surface against
the single-tail invariant.

The two genuine needs behind "insession" are met without it:

- **Reading session-scoped state** (e.g. the `todolist_action` anchor, which
  a fork cannot see — forks own their task instances): the dispatch site *is*
  parent context, so it snapshots whatever the hook needs into `kwargs`
  (anchor pks, boundary pk, trigger).
- **Writing to the parent** (marker amendments, notes, anchor updates): the
  compaction two-phase shape — fork thinks detached, an optional parent-side
  **ingest step** chained on the fork result via auto-await applies the write
  (cf. `ingest_compaction.py`, `ingest_subagent_result.py`). The ingest is a
  quick synchronous write, not an agent turn.

Anything that must *drive the parent agent loop* ("on stop, keep working")
is core-loop logic, not a hook — it belongs in `decide_next_step` directly,
like the todo auto-processing precedent
(`.agentone/scripts/core/decide_next_step.py:83-145`).

## 5. Event catalog (v1)

All dispatchers share one helper, `maybe_fire_hooks(session, event, ctx)` —
"maybe" because matcher + guards may decline. Dispatchers pass a small
context dict (anchor pks, trigger, reason); the helper resolves configured
hooks, evaluates matchers, checks guards (§8), snapshots kwargs, and
`.delay()`s the hook chain. Dispatchers never block on hooks.

### 5.1 `stop` — a turn produced its final result

- **Dispatch point:** `decide_next_step`, in the `is_final_result` branch
  (`.agentone/scripts/core/decide_next_step.py:220-241`), *after* todo
  chaining, fire-and-forget before returning the message. Must not delay the
  turn handoff to the user.
- **Semantics:** intermediate final results in a continuing session. The
  Claude `Stop`/`SubagentStop` split is expressed as a matcher on session
  type, not two events: default matcher covers `SESSION`/`SUBSESSION`;
  `SUBTASK_*` turns are excluded here (their session is about to be
  deactivated — `session_end` covers them).
- **Anchor:** `prev_message` = the final-result message. Snapshot semantics:
  a user message arriving mid-reflection is *not* included — correct for
  memory; hooks must treat the anchor as their world, never "current tail."
- **Context keys:** `message_pk` (final-result message), `session_type`,
  `has_todo_continuation` (whether a todo item was chained).

### 5.2 `pre_compact` / `post_compact` — around compaction

- **Dispatch points:** `pre_compact` at the top of `build_llm_compact_context`
  (`.agentone/scripts/compact/build_llm_compact_context.py:30`), guarded on
  `compact_attempt == 0` so retries do not refire; `post_compact` at the end
  of the `ingest_compaction` success path, after the marker is the chain tip.
- **Semantics:** the industry-standard memory pair. `pre_compact` forks see
  the doomed range with no boundary surgery (Claude's archive-transcript
  pattern); `post_compact` forks see the summary marker and receive
  `boundary_pk` for the compacted range (distill-then-forget). Pre vs post
  is dispatch order only — both are detached and race-safe via snapshot
  anchoring.
- **Context keys:** `trigger` (`auto` | `idle` | `manual` — the idle path
  passes `idle_trigger=True` today), `boundary_pk` (post only),
  `compact_attempt`.

### 5.3 `session_end` — a session deactivated

- **Dispatch point:** inside `Session.set_is_active`, on the True→False
  transition only — the single choke point covering allowlist-violation
  kills, child deactivation (`ingest_compaction`, `ingest_subagent_result`),
  work-item executor teardown, and user closes. Takes an optional
  `reason=` kwarg (backwards compatible; dispatchers that know why say so).
- **Semantics:** default matcher covers `SESSION`/`SUBSESSION`. Matching
  `SUBTASK_*` types is supported and meaningful (subagent-result
  aggregation à la Hermes `subagent_stop`), but noisy by default —
  compaction forks deactivate after every compaction, so the stock config
  excludes them.
- **Context keys:** `reason`, `session_type`, `last_message_pk`.

### 5.4 Intercept hooks — pre/post on any tool/task/command

An entry with `before:` (pre) or `after:` (post) instead of `on:` fires on
**every matching call** dispatched in the agent's sessions, regardless of
`TaskType` — tools, tasks, commands, webapi/webview share the
`TaskInstance`/`AgentTaskCall` substrate, so one hook point covers all.
`before` *is* pre, `after` *is* post; the two keys are mutually exclusive
with each other and with `on:`.

```yaml
hooks:
  - name: guard-write
    match:
      name: "filesystem-write.*"   # definition-name glob (`|`-alternation; or shorthand `match: "write*"`)
      type: tool                   # tool | task | command | webapi | webview (optional)
      session: "foobar23*"         # session-name glob (optional)
    before: validate_path          # task of the SAME agent (no cross-agent executor)
    mode: inline                   # inline | detached — both positions support both
    on_error: fail_closed          # fail_closed | fail_open (inline `before` is always fail_closed)
```

- **Filter:** `match:` dimensions are AND-combined; omitted dimensions
  (or an omitted `match:`) are wildcards. Name/agent/session are globs
  (`*`, `prefix-*`, `a1 | a2`); `type` compares case-insensitively.
- **Contract:** `before` receives the **original kwargs** and must return
  kwargs (pass-through to allow unmodified); `after` receives the
  **original result** and must return a compatible result. Inline entries
  chain in declaration order through the existing before/after-run
  machinery (`AgentTaskCall.create`, `CallScheduler.on_taskrun_ended`),
  so blocking/failure semantics are the scheduler's: a failed inline
  `before` blocks the call, a failed inline `after` cancels the parent
  unless its `on_error` is `fail_open`. Detached entries get a snapshot
  copy, are dispatched fire-and-forget, and never touch the parent.
- **Scope:** hook tasks run as the same agent in the same session (the
  declaring agent's task by name) — never in another agent's session, and
  never shared across sessions: `TaskInstance`s are per
  `(task, session, session_version)`, so concurrent sessions of one agent
  each get their own hook executions. Hook-task calls never refire
  intercepts (recursion guard), `SUBTASK_HOOK`/`SUBTASK_COMPACT` worker
  forks never fire intercepts at all, and entries merge through `extends`
  by `(name)` like lifecycle entries by `(on, name)`.

## 6. Matchers

Evaluated in `maybe_fire_hooks` before any fork is built. Plain strings match
exactly; anything else is an unanchored regex (same convention as Claude's
matcher path). Each event matches on its own fields:

| Event | Matcher fields | Examples |
|---|---|---|
| `stop` | `session_type` | `SESSION\|SUBSESSION` (default), `.*` |
| `pre_compact`, `post_compact` | `trigger` | `auto\|idle` (default), `manual`, `.*` |
| `session_end` | `session_type`, `reason` | type `SESSION\|SUBSESSION` (default); reason `deactivated`, `allowlist_violation`, … |

Rationale for matcher-first: it keeps product policy ("reflect on chat turns
but not subtask turns") in user configuration instead of `if` statements at
dispatch sites.

## 7. Handlers

### 7.1 Fork handler (v1, the only handler)

```yaml
# agent.md
hooks:
  - on: stop                    # stop | pre_compact | post_compact | session_end
    matcher: ...                # event-specific, see §6 (defaults per event)
    agent: memory               # default: self (usually a visibility: internal agent)
    task: distill_turn          # task/chain to run in the fork
    ingest: record_memory       # optional parent-side task chained on the fork result
    max_tokens: 40000           # fork context budget (§8.2)
    timeout_seconds: 300        # wall-clock deadline (§8.3)
```

Fork construction reuses the compaction fork verbatim
(`build_llm_compact_context.py:91-133`): `SUBTASK_HOOK` session (new
`SessionType` value, excluded from sidebar/chats querysets exactly like
`SUBTASK_FORK` — cf. `ui/sidebar/panels/chats.py:67`), `prev_message`
anchored per §5, workspace inherited, parent link recorded, one-off name
`p{parent_pk}:hook:{name}:{ts}` (one-off rows preserve snapshot isolation;
see §10 for the growth note). Fork settings pin: hooks disabled (recursion
guard — a hook fork's own stop/compaction/end never refires, belt-and-braces
with the `SUBTASK_HOOK` type gate in `maybe_fire_hooks`), `auto_compact_*=0`
(the fork must never idle-compact itself mid-reflection, same rationale as
compaction forks). Tool allowlist is *not* pinned to `final_result` — the
hook task needs its tools; approval-gated tools in a detached fork stall to
`HALTED_APPROVAL` unwatched, so hook agents should avoid them (lint at load:
warn when a hook agent's tools require approval).

`ingest` (optional) names a parent-side task receiving
`{hook_name, event, result}` where `result` is the fork's root call —
auto-await resolves it before the ingest runs. This is the delivery axis
(§4): absent = fire-and-forget; present = fork + parent write. It covers
every "write back" case without insession execution.

### 7.1.1 Hook task arguments (v1)

Every lifecycle hook task is dispatched with these kwargs (all hook tasks must
accept ``**kwargs``):

- `message` — the persisted framing user message in the fork (anchor).
- `hook_ctx` — a dict with `hook` (entry name), `event`, `parent_session_pk`,
  `parent_agent`, `anchor_message_pk` (the dispatch-time anchor — use this, not
  the session tail, when forking, so async siblings cannot mutate the range),
  `trigger`, `reason`.
- `hook_after` — present only when a token-budget prefix compaction ran; a
  call reference the task must wait on (auto-await) before reading context.

Event-specific `ctx` keys (passed to `maybe_fire_hooks` and mirrored into
`hook_ctx` where applicable):

- `stop`: `message_pk`, `session_type`, `has_todo_continuation`.
- `pre_compact` / `post_compact`: `trigger` (`auto`|`idle`|`manual`),
  `boundary_pk` (post only), `compact_attempt`.
- `session_end`: `reason`, `session_type`, `last_message_pk`.

### 7.2 Command handler (phase 2, not v1)

`command: path/to/script.sh` (or inline `shell:`) executed via the existing
scripts.md `SCRIPT` mode: kwargs as JSON on stdin, stdout as result,
non-zero exit = hook failure (logged, parent unaffected — Hermes/Claude
fail-open semantics). For log lines and notifications that do not justify a
fork + LLM turn.

## 8. Guards, budgets, timeouts

Evaluated in `maybe_fire_hooks` (pre-dispatch) and enforced at run time.

1. **Type gate:** `SUBTASK_HOOK` (and any future hook-spawned type) never
   fires hooks. Recursion is impossible by construction, independent of
   settings.
2. **Token budget (`max_tokens`):** estimate the fork's inherited context
   from the anchor with the existing walkers
   (`server/history_limiter.py: walk_compaction_entries`,
   `estimate_entries_tokens`). Over budget → prefix-compact the fork by
   reusing the existing `compact_if_needed` step as the hook chain's second
   step (`[build_hook_fork, compact_if_needed, <hook task>, (ingest?)]`),
   which no-ops when under budget. Rationale: skipping when over budget
   fails exactly the longest sessions a memory hook exists for; proceeding
   over budget bills a cold prefill on every firing. If no compaction
   boundary exists, proceed over budget (nothing compactable — same guard
   compaction uses).
3. **Timeout (`timeout_seconds`):** `deadline = dispatch + timeout_seconds`
   stored on the `SessionHookRun` row (§9). A tick reaper
   (`_reap_hook_timeouts`, same isolated-routine shape as the other
   `tick_scheduler` routines) transitions expired, non-ended root calls to
   `ENDED_CANCELLED` and marks the run expired. Expiry is silent by design —
   fire-and-forget has no one to report to. Cancel-call-only (the fork
   session stays inspectable, deactivated), matching industry
   fail-open/timeout-cancel semantics.
4. **Concurrency:** max one in-flight run per (session, hook name) — checked
   at dispatch against non-ended runs for the same hook; the tick never
   double-dispatches because dispatchers fire on discrete events, not scans.
5. **Per-tick cap:** hook *dispatch* happens at event sites (no tick cap
   needed), but the reaper bounds its work per tick like
  `_MAX_IDLE_COMPACTIONS_PER_TICK`.
6. **`HALTED_PAUSED`:** hooks never fire for (and reapers never touch?
   reapers only cancel hook roots, so unaffected) — for completeness, a
   `stop` hook whose parent session is paused still runs: the reflection
   describes a finished turn and pausing concerns future turns, not past
   ones. `session_end` with reason `paused`? Pausing is not deactivation —
   no event. Document both so nobody "fixes" them.

## 9. State model

```python
SessionHookRun:
    session         FK(SessionModel)      # the parent session
    hook_name       str                   # entry name from the manifest
    event           str                   # stop | pre_compact | post_compact | session_end
    anchor_message  FK(Message, null)     # snapshot anchor (§5)
    root_call       FK(AgentTaskCall, null)# hook chain root; null until dispatched
    deadline        datetime              # dispatch + timeout_seconds
    status          dispatched | ended | expired
```

Minimal by design: it exists for the reaper (§8.3) and for operators to see
what is in flight. Runs are deleted when their root call ends (or marked
`expired` by the reaper and deleted after 7 days — cheap audit trail).
No last-run pointers in v1 (no cadence triggers); if incremental anchoring
("messages since last run") is ever wanted, `anchor_message` of the previous
run is the natural cursor.

## 10. Manifest, loading, inheritance

- `hooks:` is a list of dicts on `agent.md`, inherited via `extends` like
  every other agent setting (child entries append; same `on`+`name`
  re-declared in a child replaces the parent entry; intercept entries key
  on `(none, name)`). Lifecycle entries (`on:`) and intercept entries
  (`before:`/`after:`) are mutually exclusive per entry; `before`/`after`
  must name a same-agent task, `mode` defaults to `inline` for `before`
  and `detached` for `after`, and inline `before` rejects
  `on_error: fail_open`.
- Loader validation (`registry/loader/load_agent_manifest.py`, next to the
  compaction `_validate_*` family): `on` ∈ the four events, `agent` resolves
  (default self), `task` names a task/chain visible to that agent,
  `max_tokens` / `timeout_seconds` non-negative ints. Omitted keys default
  to 40000 / 300 (explicit `0` = unbounded context / no deadline).
- Stored as `hooks` JSON on the agent version (same pattern as
  `subagent_configs`); resolved through the version chain so hooks travel
  with `extends`.
- Session-table growth: one `SUBTASK_HOOK` row per firing. Bounded in
  practice (four events, all turn-or-lifetime scoped), invisible (excluded
  from sidebar/chats querysets, deactivated on completion), and queryable
  for debugging. Reusing one session per (parent, hook) would avoid the rows
  but breaks snapshot isolation — rejected (cf. §4).

## 11. Non-goals (the sync tier, later)

V1 hooks cannot: gate or veto anything (no `PreToolUse`, no Stop-continue),
inject context into a live turn (no `additionalContext` / `pre_llm_call`
equivalent), or run synchronously in the loop. These need in-loop plumbing
(decision protocols, fail-open paths, millisecond budgets) and are a separate
design. The manifest reserves handler-type and `blocking:` keys so the sync
tier does not require a config migration — v1 rejects `blocking: true` at
load with a clear error.

Also out of scope: cadence triggers (`every_N_messages/tokens/seconds` —
revisit only with a demonstrated need; events cover the known use cases),
hook chaining (a hook firing another hook — prohibited by the §8.1 type
gate), and UI surfacing (hook runs are visible in Django admin via
`SessionHookRun`; chat UI shows only parent-side ingest effects).

## 12. Testing plan

- **Loader:** `LoadHooksTest` — valid block, bad `on`, unresolvable agent,
  unknown task, negative budget/timeout, `blocking: true` rejected;
  inheritance append + replace fixtures (same shape as the visibility/
  compaction-settings fixtures).
- **Dispatch:** unit tests per event at the choke point with a recording
  hook agent — `stop` fires for `SESSION` but not `SUBTASK_FORK`;
  `pre_compact` fires once across retries (`compact_attempt` 0 vs 1);
  `post_compact` carries `boundary_pk`; `session_end` fires only on the
  True→False transition (double `set_is_active(False)` fires once).
- **Matcher:** table-driven event × matcher → fires/declines.
- **Recursion:** a hook fork's stop/compaction/end never dispatches
  (type gate), even with hooks configured on the hook agent.
- **Budget:** over-budget fork gets the `compact_if_needed` prefix step;
  under-budget skips it; no-boundary proceeds.
- **Timeout:** reaper cancels expired non-ended roots, leaves ended ones,
  marks runs expired; cap per tick.
- **Snapshot:** user message appended after dispatch is not visible to the
  hook fork (anchor fixed at dispatch).
- **Regression:** full compaction/fork suites stay green (dispatch points
  live in `decide_next_step`, `build_llm_compact_context`,
  `ingest_compaction`).

## 13. Rollout

1. **V1 (this doc):** model + loader + `maybe_fire_hooks` + four events +
   fork handler + reaper + tests. Stock `baseagent` declares no hooks —
   the framework ships the mechanism default-off; memory agents opt in.
2. **Command handlers** (§7.2) for cheap hooks.
3. **Sync tier** (§11) as its own design doc once async hooks prove the
   event/matcher vocabulary.

---

**See also:** [Manifest format](manifest-format.md) · [Architecture](architecture.md) · [Core mechanisms](core-mechanisms.md)
