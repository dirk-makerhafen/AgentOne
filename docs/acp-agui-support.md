# ACP and AG-UI Support — Feasibility Report

**Originally written:** 2026-09-09 · **Updated:** 2026-11-21 · **Status:** report only, no code changed ·
**Scope:** feasibility + implementation plan · **ACP target:** v1 stable

Two open protocols could connect AgentOne to outside clients:

| | ACP (Agent Client Protocol) | AG-UI (Agent–User Interaction Protocol) |
|---|---|---|
| Origin | Zed-led, editors + coding agents | CopilotKit, agents + frontends |
| Transport | JSON-RPC 2.0 over stdio (local) or HTTP/WS (remote, maturing) | `POST RunAgentInput` → SSE event stream (WS/binary also allowed) |
| Shape | Request/response methods + notifications | ~16 typed events (`RUN_*`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `STATE_*`, …) |
| Our role | **Agent side** (editors drive us) | **Agent backend** (`HttpAgent` clients drive us) |
| Spec | `agentclientprotocol.com`, stable v1 (v2 draft Jul 2026) | `docs.ag-ui.com`, Apache 2.0, Python/TS SDKs |

Both remain feasible. The main shared prerequisite is still **fine-grained live
turn events** (token/tool-call deltas) that external protocol adapters can
consume. Since 2026-09-09, the internal UI event system changed substantially,
but not in a way that removes that prerequisite. This update refreshes code
references, architecture assumptions, and gaps against the current codebase. It
makes no priority recommendation; §7 lists the decision factors.

---

## 1. How AgentOne works today (relevant subset)

- **Server:** Django monolith + Celery (worker + beat) + Redis (channels, cache,
  broker). ASGI serves HTTP through Django and one UI WebSocket route:
  `^app/ws/events/$` (`config/asgi.py:18-23`). REST lives at `api/v1/`
  (`config/urls.py:20-26`).
- **UI:** the old pyHtmlGui global-instance UI has been replaced by the
  server-rendered htmx/SSE-style component UI. `webui/core/events.py`
  implements a WebSocket transport with an EventSource-shaped payload
  (`{"event": ..., "data": ...}`) so htmx `sse:` triggers still work. The
  legacy HTTP `/app/sse/` view remains only as fallback; the UI connects to the
  WebSocket. See `docs/ui-rewrite.md`, `docs/htmx-sse.md`, and
  `docs/observables-migration.md`.
- **Observable events:** `server/models/observables.py` is a Redis-backed
  per-tab watch registry. Models publish explicit keys via
  `publish_model_event(...)` on commit; `_fan_out()` delivers only to tabs
  watching those keys. Events carry key/action/data hints, not rendered HTML.
  This is a UI invalidation bus, not a generic per-token protocol stream.
- **Sessions:** `SessionModel` (identity) + `SessionVersion` (copy-on-write state);
  runtime facade `runtime/session/session.py` (`Session.add_user_message(...)`,
  `get_task/get_tool/get_command`, allowlists, `set_is_active`, `fork`,
  `spawn_subagent`). Slash commands are routed by `add_user_message` when the
  first part starts with `/`.
- **LLM turn pipeline** (`.agentone/scripts/core/`): `ingest_user_message` →
  `build_llm_context` → `call_llm` (LiteLLM `stream=True`) →
  `parse_llm_response` → `ingest_assistant_message` (dispatches tool/task calls).
  `call_llm.py` accumulates chunks in memory, checkpoints `Response.save(...)`
  roughly every second, and publishes a throttled partial row-key update for the
  active response component. It does **not** publish per-token protocol events.
  Full flow: `docs/core-mechanisms.md`.
- **External API:** DRF under `api/v1/` with JWT auth (`TokenObtainPairView`,
  `TokenRefreshView`, DRF spectacular docs). Sessions expose
  `POST /api/v1/sessions/{id}/message/` (accepts `content` or `parts`, returns
  query data, 201), `GET /messages/`, `GET /tasks/`, and session settings
  patching. Task calls expose `POST /task-calls/{id}/approve|deny|answer`.
  There is still no ACP JSON-RPC adapter and no AG-UI SSE run endpoint.
- **Launcher:** remote *tool executor* (FastAPI, `POST /shell|/python|/direct`,
  `X-API-Key`), not an agent runner — ACP remote-agent hosting would be new.

## 2. ACP v1 — what it would take

### 2.1 Protocol surface (agent side)

Baseline methods we must implement: `initialize` (negotiate `protocolVersion` +
capabilities), `authenticate` (iff we require it), `session/new`,
`session/prompt`. Optional but expected by real clients: `session/load`
(needs `loadSession` capability), `session/cancel`, `session/request_permission`
(agent→client bidirectional request used for approvals), `session/update`
(agent→client notifications: text chunks, thoughts, tool-call upserts).

Transports: **stdio subprocess** is the primary pattern (editor boots us per
connection, multiple concurrent sessions per connection); HTTP/WS remote mode
is still maturing upstream.

### 2.2 Fit: AgentOne concepts map well

| ACP concept | AgentOne counterpart |
|---|---|
| Session | `SessionModel` + `SessionVersion`; resume ≈ pin existing session/version (`session/load`) |
| `session/prompt` | `Session.add_user_message(message, execute_turn=...)` (`runtime/session/session.py`) → existing `process_turn` chain; also handles slash-command routing and scheduler strategies |
| `session/cancel` | Session/query cancel path (`runtime/session/session.py:stop_generation`, Query/TaskCall cancellation APIs) plus scheduler `interrupt` strategy |
| `session/request_permission` | Approval-gated task calls. Current paths: guardrail/allowlist decisions in `runtime/tasks/call_scheduler.py`, FSM transitions in `runtime/tasks/call_fsm.py` (`HALTED_APPROVAL`), REST approve/deny/answer in `api/views/tasks.py` |
| Tool calls in `session/update` | `AgentTaskCall`/`AgentTaskRun` lifecycle; read APIs exist under `api/v1/task-calls/` and `task-runs/` |
| `initialize` capabilities | Resolved agent caps (`latest_agent_version`, allowlists, tool availability via runtime agent/session facades) |
| Absolute-path rule | Matches workspace realpath handling and filesystem guardrails |

### 2.3 Gaps

1. **No JSON-RPC layer.** No stdio adapter, no ACP route/dispatcher, no ACP SDK
   integration. A Python SDK exists (`agentclientprotocol/python-sdk`) — use it,
   don't hand-roll framing/method dispatch.
2. **No external streaming notifications.** `session/update` text/tool-call
   chunks need the shared live-event prerequisite (§4). Current
   `publish_model_event`/WebSocket UI events are keyed invalidations for the
   htmx UI, not an ACP event protocol.
3. **Permission round-trips.** Approvals are currently resolved inside AgentOne:
   UI cards and REST endpoints call `TaskCallStateMachine.approve()` /
   `CallScheduler.deny_taskcall()` / `answer_question_call()`. Over ACP,
   `session/request_permission` is a blocking bidirectional client request;
   parked calls must wait without wedging scheduler ticks, retries, or timeouts.
4. **Auth mapping.** `authenticate` must map to a Django user/token scope so
   sessions, workspaces, and keys stay isolated. JWT exists for REST, but stdio
   ACP clients will not naturally speak it; likely a local stdio trust model plus
   optional API-key/client binding for remote modes.
5. **v1/v2 drift.** ACP v2 draft changes prompt lifecycle semantics and removes
   client FS/terminal in favour of MCP. Build v1 first, but keep the protocol
   mapping layer thin and isolate ACP method translation from core runtime logic.

### 2.4 Implementation sketch (Phase A)

- **A0 (shared):** live turn-event prerequisite (§4).
- **A1 — stdio adapter (new package, e.g. `acp/`):** process entrypoint using the
  Python SDK; method handlers: `initialize` → caps from agent/version;
  `session/new` → create `SessionModel` (+ version); `session/prompt` →
  `add_user_message(...)` and stream back `session/update` from a protocol event
  source; `session/cancel` → existing cancellation path; `session/load` →
  rebind existing session.
- **A2 — permissions:** park-and-resume in the call FSM wiring
  `session/request_permission` to existing approval data (task call, args,
  guardrail reason, allow/deny/answer options as applicable).
- **A3 — packaging:** manifest/agent config/docs for editor setup (boot command,
  env keys, auth model); tests with a fake JSON-RPC stdio client covering prompt,
  cancel, permission, and reconnect/load behavior.

## 3. AG-UI — what it would take

### 3.1 Protocol surface (backend side)

One endpoint: accept `POST` with `RunAgentInput`
(`threadId`, `runId`, `messages`, `tools`, `state`, `context`), respond
`text/event-stream` with ordered events. Protocol rules that constrain us:
every run MUST open with `RUN_STARTED` and close with `RUN_FINISHED`/`RUN_ERROR`;
`TEXT_MESSAGE_CONTENT.delta` must be non-empty; tool events link by
`toolCallId`; `STATE_DELTA` is RFC 6902 JSON Patch; runs are sequential per
thread. `@ag-ui/encoder` (`EventEncoder`) handles SSE framing; `RAW`/`CUSTOM`
cover anything proprietary.

### 3.2 Fit: AgentOne concepts map well

| AG-UI concept | AgentOne counterpart |
|---|---|
| Thread / run | `SessionModel` / `Query`+`Response` turn (`RUN_STARTED` ≈ `Query ACTIVE`/turn accepted, close ≈ terminal query/response state) |
| `TEXT_MESSAGE_*` | Assistant message parts produced by `call_llm.py` / `ingest_assistant_message.py` |
| `TOOL_CALL_START/ARGS/END` | `AgentTaskCall` creation/arg normalization/terminal lifecycle in task FSM + ingestion pipeline |
| `STATE_SNAPSHOT/DELTA` | Session state (`is_active`, context usage, scheduler/tool state), task-call status; current system exposes reads, not protocol deltas |
| `MESSAGES_SNAPSHOT` | `GET /api/v1/sessions/{id}/messages/` (paginated DRF endpoint) |
| Frontend tools / HITL | Approval cards / `ask_user` answer flow (`task-calls/{id}/approve|deny|answer`) and user interrupt strategies |
| Auth | Existing DRF JWT — `HttpAgent` can send `Authorization: Bearer` |

### 3.3 Gaps

1. **No AG-UI SSE endpoint.** New view (e.g. `POST /api/v1/ag-ui/runs`) with
   `StreamingHttpResponse` or ASGI streaming, SSE framing, heartbeat, and
   run→`Query` bookkeeping. Current WebSocket UI events are not AG-UI-compatible.
2. **No external streaming events** (§4) — same prerequisite as ACP. Chunked
   response checkpoints exist, but they are row updates, not AG-UI event frames.
3. **Run/thread bookkeeping.** `threadId`↔session and `runId`↔query mapping,
   sequential-run enforcement per thread, reconnect/replay policy, and
   `TOOL_CALL_RESULT` re-entry (client returns tool results; agent continues).
4. **State deltas.** We have full-state reads everywhere; emitting minimal
   RFC 6902 patches needs a differ at a deliberately small state root. Start
   with `STATE_SNAPSHOT` and only add deltas for stable, high-value slices.

### 3.4 Implementation sketch (Phase B)

- **B0 (shared):** live turn-event prerequisite (§4).
- **B1 — SSE endpoint:** DRF/ASGI endpoint + AG-UI encoder-compatible framing
  (dependency or small vendored encoder), JWT auth, `threadId`→session
  resolution (create-or-bind), emit `RUN_STARTED` on accepted turn/query.
- **B2 — event mapping:** chunk→`TEXT_MESSAGE_*`, tool-call lifecycle →
  `TOOL_CALL_*`, terminal→`RUN_FINISHED`/`RUN_ERROR`, `MESSAGES_SNAPSHOT` from
  existing history/message serialization.
- **B3 — state + re-entry:** `STATE_SNAPSHOT` on open, deltas for a small chosen
  slice, `TOOL_CALL_RESULT` ingestion continuing the turn, cancel mapped to
  existing query/session cancellation.
- **B4 — client validation:** test against `HttpAgent` (TS) and/or Python
  client; keep raw event logs for replay/debugging.

## 4. Shared prerequisite: live turn events (Phase 0, do first)

**Problem.** `call_llm.py` streams LiteLLM deltas in a Celery worker, accumulates
`response.content`/`reasoning`/`tool_calls`, and checkpoint-saves the `Response`
about every second. During that checkpoint it also publishes a throttled
row-key update for the response component:

```py
response.save(publish=False)
publish_model_event(partial_row_keys(response), response, "update")
```

That is useful for the current htmx UI, but it is not enough for ACP or AG-UI:
both need ordered, fine-grained turn events (text deltas, thought/reasoning
deltas where exposed, tool-call arg/start/end, terminal status). The UI event
system also intentionally carries invalidation hints, not rendered payloads and
not protocol-specific event envelopes.

**What changed since the original report.** The old pyHtmlGui `ui/consumer.py`
pump and `CHANNEL_GROUP` model-observer fan-out are gone. The current system is
`server/models/observables.py` + `webui/core/events.py` (WebSocket transport for
htmx `sse:` triggers) + component refetches. This simplifies UI delivery, but it
does not remove the need for a protocol event source.

**Plan.**

1. **Define a protocol-neutral turn-event shape.** Do not overload
   `publish_model_event` key invalidations with token streams. Add a dedicated
   event path (e.g. Redis pub/sub channel per session/run/query, or a small
   append/read stream abstraction) carrying ordered events with sequence ids,
   run/session/query ids, timestamps, and typed payloads.
2. **Emit from the chunk loop in `call_llm.py`.** Hook the existing stream loop
   where content/reasoning/tool-call chunks are accumulated. Throttle/coalesce
   text deltas (e.g. 10–20 Hz or N chars) to bound Redis traffic; preserve order.
   Emit lifecycle events for response start, tool-call argument growth/start/end
   as available, terminal success/failure/cancel, and optionally usage/context.
3. **Keep UI invalidations separate by default.** The existing response row-key
   invalidation can remain for the htmx UI. Protocol adapters should consume the
   dedicated turn-event stream, not scrape component refetches. Reusing the same
   source events for UI live rendering is possible later, but should be a
   deliberate follow-up, not an accidental coupling.
4. **Measure overhead and delivery semantics.** Check chunk→client latency,
   Redis volume under long streams, ordering under concurrent sessions, and idle
   cost when no ACP/AG-UI consumer is attached. Gate emission/publish work on
   active subscribers where possible.

Phase 0 is independently valuable: it can also enable live token rendering in
AgentOne's own UI later, but the primary deliverable is a clean event source for
protocol adapters.

## 5. Effort estimate (rough, backend-dev days)

| Phase | Work | Size |
|---|---|---|
| 0 | Live turn-event source + chunk hook + overhead/load check | 4–6 |
| A1 | ACP stdio adapter, baseline methods | 5–8 |
| A2 | ACP permission park-and-resume in FSM/call scheduler | 3–5 |
| A3 | ACP packaging, docs, fake-client tests | 2–3 |
| B1 | AG-UI SSE endpoint + auth + thread/run bookkeeping | 3–5 |
| B2 | AG-UI event mapping (text/tool/lifecycle/history) | 3–5 |
| B3 | AG-UI state snapshots/deltas + `TOOL_CALL_RESULT` re-entry + cancel | 4–6 |
| B4 | AG-UI client validation + replay logs | 2–3 |

Totals: ACP ≈ 14–22 d (after Phase 0); AG-UI ≈ 12–19 d (after Phase 0).
Phase 0 de-risks both; A and B tracks are independent after it. The Phase 0
range increased slightly because the old report assumed adding onto a now-removed
consumer/broadcast model; the new work should create a clean protocol event path
instead of piggybacking on UI invalidations.

## 6. Risks and open questions

1. **Worker→client fan-out latency.** Chunks originate in Celery workers;
   SSE/stdio sinks live in web/adapter processes. Redis pub/sub or an equivalent
   stream bridge is the likely path, but ordering, reconnect semantics, and
   backpressure under concurrent sessions need testing.
2. **Permission round-trips (ACP).** Blocking on an editor user's click interacts
   with scheduler ticks, task timeouts, and cancellation semantics. Needs an
   explicit parked-approval design (FSM detail/state, timeout behavior, cancel
   behavior, and visible `session/update` or equivalent status).
3. **UI event bus is not a protocol bus.** The current observables/WebSocket
   system is optimized for keyed UI invalidation. Reusing it directly for ACP or
   AG-UI would couple protocol correctness to UI watch keys and component
   refetch behavior. Keep protocol event streams separate.
4. **ACP remote mode is immature upstream.** stdio-first is safe; HTTP/WS hosting
   may chase a moving spec. Prefer stdio + document remote as experimental.
5. **Key/model scoping for external clients.** Which providers/keys/models may an
   ACP editor session or AG-UI thread spend? Needs a scope model (per-client key
   set, allowed models, or spend caps) before exposing either beyond localhost.
6. **v1 vs v2 (ACP).** v2 draft changes prompt lifecycle behavior and removes
   client FS/terminal in favor of MCP. Build v1 now if needed, but keep the
   adapter's method layer thin so v2 is a mapping change, not a rewrite.
7. **Test doubles.** Both tracks need fake counterparties (JSON-RPC stdio client;
   SSE event consumer) in `server/tests/` or `api/tests/`, plus ordering/replay
   tests for chunked tool-call and terminal events.

## 7. Decision factors (no recommendation)

- **Choose ACP first if:** editor integration (Zed-family, ACP clients) is the
  strategic goal; stdio distribution fits (no inbound ports, per-connection
  isolation); permission-gated coding tasks are the flagship flow.
- **Choose AG-UI first if:** web/mobile/chat frontends matter more; the existing
  DRF+JWT stack makes an HTTP SSE endpoint a natural fit; CopilotKit/`HttpAgent`
  ecosystem reach is attractive; generative-UI ambitions (A2UI/MCP-Apps riding on
  AG-UI as the runtime layer) are on the roadmap.
- **Either way:** do Phase 0 first — it pays off for both tracks and for
  AgentOne's own future live rendering, but it should be implemented as a clean
  protocol event source, not by overloading the htmx/UI invalidation bus.

## 8. Update notes (2026-11-21)

Key codebase changes reflected in this revision:

- **UI transport changed:** old pyHtmlGui/global `ui/consumer.py` assumptions are
  obsolete. The UI now uses htmx components with a per-tab WebSocket event stream
  (`webui/core/events.py`, `/app/ws/events/`, fallback `/app/sse/` view exists).
- **Observable model changed:** `server/models/observables.py` is now a
  Redis-backed key watch registry with explicit `publish_model_event` keys and
  commit-time fan-out; there is no `CHANNEL_GROUP` broadcast.
- **Session/runtime API evolved:** `Session.add_user_message(...)` remains the
  main ingress, but it now normalizes flexible message specs, routes slash
  commands, supports scheduler strategies, and has `fork`/`spawn_subagent`
  workflows. Old line-number references in this doc were stale.
- **LLM streaming still accumulates in worker:** `call_llm.py` still streams via
  LiteLLM and checkpoint-saves responses every ~1s. It now also publishes a
  throttled partial row-key invalidation for the response component; that helps
  the UI but is not a protocol-grade token/event stream.
- **API surface moved:** DRF is mounted at `api/v1/` (`config/urls.py`), not the
  old `/api/v0.1/` shape implied by stale references. There is still no ACP or
  AG-UI endpoint.
- **Approval flow is explicit:** task-call approval/deny/answer endpoints exist in
  `api/views/tasks.py`; ACP permission bridging would still need parked
  bidirectional request handling.
