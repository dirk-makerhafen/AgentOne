# ACP and AG-UI Support — Feasibility Report

**Date:** 2026-09-09 · **Status:** report only, no code changed ·
**Scope:** feasibility + implementation plan · **ACP target:** v1 stable

Two open protocols could connect AgentOne to outside clients:

| | ACP (Agent Client Protocol) | AG-UI (Agent–User Interaction Protocol) |
|---|---|---|
| Origin | Zed-led, editors + coding agents | CopilotKit, agents + frontends |
| Transport | JSON-RPC 2.0 over stdio (local) or HTTP/WS (remote, maturing) | `POST RunAgentInput` → SSE event stream (WS/binary also allowed) |
| Shape | Request/response methods + notifications | ~16 typed events (`RUN_*`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `STATE_*`, …) |
| Our role | **Agent side** (editors drive us) | **Agent backend** (`HttpAgent` clients drive us) |
| Spec | `agentclientprotocol.com`, stable v1 (v2 draft Jul 2026) | `docs.ag-ui.com`, Apache 2.0, Python/TS SDKs |

Both are feasible. Neither is free: they share one prerequisite —
**per-token streaming events** — that does not exist in the codebase today.
This report maps the fit, names the gaps, and sketches phased plans for each
track. It makes no priority recommendation; §7 lists the decision factors.

---

## 1. How AgentOne works today (relevant subset)

- **Server:** Django monolith + Celery (worker + beat) + Redis (channels, cache,
  broker). ASGI router exposes a single WebSocket route `ws`
  (`config/asgi.py:14-18`); REST lives at `api/v1/` (`config/urls.py:90`).
- **UI:** one global pyHtmlGui instance over that socket. The Redis→UI pump
  (`ui/consumer.py:23-71`) and `UiApp.dispatch_session_event`
  (`ui/app.py:46-56`) fan model changes out to views via `ModelObserver`
  (`ui/model_observer.py:24-124`).
- **Sessions:** `SessionModel` (identity) + `SessionVersion` (copy-on-write state);
  runtime facade `runtime/session/session.py` (`Session.add_user_message()`,
  `get_task/get_tool/get_command`, allowlists, `set_is_active`).
- **LLM turn pipeline** (`.agentone/scripts/core/`): `ingest_user_message` →
  `build_llm_context` → `call_llm` (LiteLLM `stream=True`) →
  `parse_llm_response` → `ingest_assistant_message` (dispatches tool/task calls).
  Full flow: `docs/core-mechanisms.md`.
- **External API:** DRF `api/` with 13 resources, JWT (`Session + Bearer`,
  `config/settings.py:157-177`), OpenAPI docs. `sessions/{id}/message/` accepts
  parts and returns the created query (201); `sessions/{id}/call/<task_name>/`
  dispatches a task and returns `{call_id, url}` for **polling**. There is no
  SSE or streaming endpoint today.
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
| `session/prompt` | `Session.add_user_message(parts)` (`runtime/session/session.py:703`) → existing `process_turn` chain |
| `session/cancel` | Query cancel path (`api/views/queries.py`) / `interrupt` strategy (`runtime/session/session.py:815-842`) |
| `session/request_permission` | Approval cards + allowlist gate (`tool_allowlist_violated`, session abort); `AUTO_REVIEW_TOOL_NAMES` in `runtime/tasks/call_scheduler.py:25` |
| Tool calls in `session/update` | `AgentTaskCall`/`AgentTaskRun` lifecycle (`task-calls/`, `task-runs/` API already read-only) |
| `initialize` capabilities | Resolved agent caps (`latest_agent_version`, allowlists via `runtime/agents/agent.py`) |
| Absolute-path rule | Matches our workspace realpath handling |

### 2.3 Gaps

1. **No JSON-RPC layer.** No stdio adapter, no `acp/` route, no method dispatcher.
   A Python SDK exists (`agentclientprotocol/python-sdk`) — use it, don't hand-roll.
2. **No streaming notifications.** `session/update` text/tool-call chunks need the
   shared streaming-event prerequisite (§4).
3. **Permission round-trips.** Today's approvals render as cards in our UI and
   resolve in-process. Over ACP, `session/request_permission` is a blocking
   bidirectional JSON-RPC call to the *client*; the tick/task FSMs
   (`runtime/tasks/call_fsm.py`, `run_fsm.py`) currently assume local resolution.
   Needs a pending-permission state that parks the call without failing the tick.
4. **Auth mapping.** `authenticate` must map to a Django user / token scope so
   sessions, workspaces, and keys stay isolated. JWT machinery exists but ACP
   clients won't speak it over stdio — likely API-key-per-client like the
   launcher's `X-API-Key` pattern.
5. **Client FS/terminal removal (v2 note).** v2 draft drops `fs/*` in favour of
   MCP. Targeting v1 avoids this; a v2 migration would need an MCP bridge for
   file access instead.

### 2.4 Implementation sketch (Phase A)

- **A0 (shared):** streaming-event prerequisite (§4).
- **A1 — stdio adapter (new package, e.g. `acp/`):** process entrypoint using the
  Python SDK; method handlers: `initialize` → caps from agent version;
  `session/new` → create `SessionModel` (+ version); `session/prompt` →
  `add_user_message()` and stream back `session/update` from the event bus;
  `session/cancel` → cancel path; `session/load` → rebind existing session.
- **A2 — permissions:** park-and-resume in the call FSM wiring
  `session/request_permission` to the existing approval data (title, subject,
  allow/deny options).
- **A3 — packaging:** manifest/skill entry so an agent definition can advertise
  ACP; document editor setup (boot command, env keys); tests with a fake client
  speaking JSON-RPC over stdio.

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
| Thread / run | `SessionModel` / `Query`+`Response` turn (`RUN_STARTED` ≈ `Query ACTIVE`, close ≈ terminal status) |
| `TEXT_MESSAGE_*` | Assistant message parts (`ingest_assistant_message.py`) |
| `TOOL_CALL_START/ARGS/END` | `AgentTaskCall` create → arg normalize → terminal (`call_llm.py:292-297`, `parse_llm_response.py:138`) |
| `STATE_SNAPSHOT/DELTA` | Session state / `set_is_active`, context usage (`runtime/session/session.py:863-926`) |
| `MESSAGES_SNAPSHOT` | `sessions/{id}/messages/` (already paginated) |
| Frontend tools / HITL | Approval cards; user interrupt (`interrupt` strategy) |
| Auth | Existing DRF JWT — `HttpAgent` can already send `Authorization: Bearer` |

### 3.3 Gaps

1. **No SSE endpoint.** New view (e.g. `POST /api/v1/ag-ui/runs`) with
   `StreamingHttpResponse`, SSE framing, heartbeat, and run→`Query` bookkeeping.
2. **No streaming events** (§4) — same prerequisite as ACP.
3. **Run/thread bookkeeping.** `threadId`↔session and `runId`↔query mapping,
   sequential-run enforcement per thread, and `TOOL_CALL_RESULT` re-entry
   (client returns tool results; agent continues) — the closest existing shape
   is the `call_id` + `result_url` polling pair in the legacy web API
   (`config/urls.py:17-83`), which can inform the design but isn't reusable as-is.
4. **State deltas.** We have full-state reads everywhere; emitting minimal
   RFC 6902 patches needs a differ at the chosen state root (session header?
   context usage? task list?). Start with `STATE_SNAPSHOT` + deltas only for a
   small, well-defined slice.

### 3.4 Implementation sketch (Phase B)

- **B0 (shared):** streaming-event prerequisite (§4).
- **B1 — SSE endpoint:** DRF view + `EventEncoder`-compatible framing
  (dependency or vendored 50-line encoder), JWT auth, `threadId`→session
  resolution (create-or-bind), emitting `RUN_STARTED` on `Query ACTIVE`.
- **B2 — event mapping:** chunk→`TEXT_MESSAGE_CONTENT`, tool-call lifecycle →
  `TOOL_CALL_*`, terminal→`RUN_FINISHED`/`RUN_ERROR`, `MESSAGES_SNAPSHOT` from
  existing history serializer.
- **B3 — state + re-entry:** `STATE_SNAPSHOT` on open, deltas for the chosen
  slice, `TOOL_CALL_RESULT` ingestion continuing the turn, cancel via existing
  query cancel.
- **B4 — client validation:** test against `HttpAgent` (TS) and/or Python client;
  log-and-replay a run from the event stream (AG-UI's debuggability is a
  selling point — keep raw event logs).

## 4. Shared prerequisite: streaming events (Phase 0, do first)

**Problem.** The LiteLLM stream loop accumulates deltas in the Celery worker and
checkpoint-saves `Response` ~1×/sec *silently* (`call_llm.py:169-173, 207-273`).
The UI learns about turns only at coarse boundaries (`Query create` in
`build_llm_context.py:140-141`, `Query update` on terminal states in
`call_llm.py:448-459`). Both protocols need per-chunk visibility.

**Plan.**

1. Add `publish_token_event()` / `publish_agui_event()` beside
   `publish_model_event()` in `runtime/events.py:73-94`, reusing `CHANNEL_GROUP`
   (`runtime/events.py:28`) and `_extract_filter_context`.
2. Hook the chunk loop (`call_llm.py:207-273`): emit text deltas + tool-call-arg
   deltas; throttle to ~10–20 Hz or N characters to bound Redis traffic.
   Alternative hook: `Response.save()` throttled path — coarser, less code.
3. Consume: ACP adapter subscribes for `session/update`; AG-UI endpoint
   subscribes per-run for event translation. The existing consumer pump
   (`ui/consumer.py:23-71`) is pyHtmlGui-internal and should **not** be reused
   for wire serialization — new serializers per protocol.
4. Measure: chunk→client latency, Redis volume under a long stream, behaviour
   when no external client is attached (must be near-zero overhead — gate on
   active subscriptions).

Phase 0 is independently shippable and also unlocks live token rendering in our
own UI later.

## 5. Effort estimate (rough, backend-dev days)

| Phase | Work | Size |
|---|---|---|
| 0 | Streaming-event bus + chunk hook + load check | 3–5 |
| A1 | ACP stdio adapter, 4 baseline methods | 5–8 |
| A2 | Permission park-and-resume in FSMs | 3–5 |
| A3 | Packaging, docs, fake-client tests | 2–3 |
| B1 | SSE endpoint + auth + thread/run bookkeeping | 3–5 |
| B2 | Event mapping (text/tool/lifecycle/history) | 3–5 |
| B3 | State snapshots/deltas + `TOOL_CALL_RESULT` re-entry + cancel | 4–6 |
| B4 | `HttpAgent` validation + replay logs | 2–3 |

Totals: ACP ≈ 13–21 d (after Phase 0); AG-UI ≈ 12–19 d (after Phase 0).
Phase 0 de-risks both; A and B tracks are independent after it.

## 6. Risks and open questions

1. **Worker→client fan-out latency.** Chunks originate in Celery workers; SSE/stdio
   sinks live in web/adapter processes. Redis pub/sub bridges them, but ordering
   and backpressure under concurrent sessions need testing.
2. **Permission round-trips (ACP).** Blocking the agent on an editor user's click
   interacts badly with the 10s tick and task timeouts — needs explicit design
   (park state, tick exemption, timeout surfacing as `session/update`).
3. **ACP remote mode is immature upstream.** stdio-first is safe; HTTP/WS hosting
   may chase a moving spec. Prefer stdio + document remote as experimental.
4. **Key scoping for external clients.** Which providers/keys may an ACP editor
   session or AG-UI thread spend? Needs a scope model (per-client key set or
   spend caps) before exposing either beyond localhost.
5. **v1 vs v2 (ACP).** v2 draft changes the prompt lifecycle (ack + async
   `session/update`), unifies tool-call upserts, and removes client FS/terminal.
   Building v1 now is fine, but keep the adapter's method layer thin so v2 is a
   mapping change, not a rewrite.
6. **Test doubles.** Both tracks need a fake counterparty (JSON-RPC stdio client;
   SSE event consumer) in `server/tests/` or `api/tests/` — plan for them, not
   manual-only verification.

## 7. Decision factors (no recommendation)

- **Choose ACP first if:** editor integration (Zed-family, ACP clients) is the
  strategic goal; stdio distribution fits (no inbound ports, per-connection
  isolation); permission-gated coding tasks are the flagship flow.
- **Choose AG-UI first if:** web/mobile/chat frontends matter more; the existing
  DRF+JWT stack makes an SSE endpoint cheap; CopilotKit/`HttpAgent` ecosystem
  reach is attractive; generative-UI ambitions (A2UI/MCP-Apps ride on AG-UI as
  the runtime layer) are on the roadmap.
- **Either way:** do Phase 0 first — it pays off for both tracks and for our own
  UI's future live rendering.
