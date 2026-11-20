# Observables — write-side keys, read-side API, per-tab SSE

> **Status: implemented.** Every ORM row publishes an explicit list of keys;
> every connected browser tab renders a set of components, each of which
> subscribes to the keys it needs. Redis fans an event out only to the tabs
> that registered that key. There is no broadcast, no callback registry, and
> no client-side invalidation logic.

The legacy pyHtmlGui app (`ui/`) is gone; `webui/` is the only UI. See
[`ui-rewrite.md`](ui-rewrite.md) for the rendering/component side and
[`ui-implementation-guide.md`](ui-implementation-guide.md) for the normative
rules and agent checklist.

## Stages

| Stage | File | Mechanism |
|---|---|---|
| Publish | `server/models/observables.py` | `ObservableMixin.save()` / `delete()` / `atomic_update()` / `atomic_update_by_pk()` call `notify_observers()`, which calls `publish_model_event(keys, instance, action)`. The event is deferred with `transaction.on_commit`, so a component can never refetch a pre-commit row. |
| Keys | `runtime/observable_keys.py` | One explicit builder per model produces the exact strings. Nothing is derived by introspecting the model at publish time. |
| Fan-out | `server/models/observables.py` | `_fan_out()` looks up `agentone:sse:keys:<key>` → client ids, drops dead clients, and `PUBLISH`es one JSON message per tab channel. |
| Transport | `webui/events.py` | `GET /app/sse/?client=<id>` streams only that tab's events; `POST /app/sse/watch` replaces the tab's watch set. |
| Subscribe | `webui/components.py` | Each component wrapper carries `hx-trigger="sse:<key> delay:150ms, …"`; the browser derives the watch set from those triggers and posts it when it changes. |

## Key grammar

```
Model:<pk>                    one row
Model.<relation>:<id>         a foreign-key scoped list
Model.root                    rows with no parent_*
<key>@<field>:<value>         an explicit filter variant
```

`@` separates filter suffixes from the base key. Keys never contain `[`, `,`
or whitespace, because htmx tokenises `hx-trigger` on those and the key is used
verbatim as an SSE event name.

Every publisher also emits the **bare model key** (`Message`, `SessionModel`,
…). That is the subscription for lists that only ever show "all rows of this
model"; it removes the need for a generic "any key" filter.

Examples:

| Write | Keys |
|---|---|
| `Message` in session 7 | `Message`, `Message:42`, `Message.session:7`, `Message.session_version:3` |
| Root `SessionModel` archived | `SessionModel`, `SessionModel:7`, `SessionModel.root@is_archived:true`, `SessionModel.root@is_archived:false`, `SessionModel@is_active:true` |
| `WorkItem` moved to `done` | `WorkItem`, `WorkItem:9`, `WorkItem.project:4@terminal:true`, `WorkItem.project:4@terminal:false`, … |

### Both old and new values

A filter transition publishes both sides:

```python
observable_keys(session, {"is_archived": False, "is_active": True})
# ... SessionModel.root@is_archived:true   <- add to archived list
# ... SessionModel.root@is_archived:false  <- remove from active list
```

Without the previous value an archived row could only ever be *added* to the
archived view and would stay in the active view forever.

`ObservableMixin._previous_state()` snapshots every FK and every filter field
(`is_active`, `is_archived`, `is_pinned`, `session_type`, `status`,
`verify_status`) before `save()`. `atomic_update_by_pk()` reads the previous
row from the database; `atomic_update()` snapshots the instance.

```python
class ObservableMixin:
    def notify_observers(self, action="update", previous=None):
        publish_model_event(observable_keys(self, previous), self, action)
```

The dispatch table in `runtime/observable_keys.py` maps model name → builder.
A model without an entry falls back to `Model` + `Model:<pk>` (row-only).

## Read side

`runtime/observable_queries/` is the only place a view may obtain live data.
Each method returns an `ObservableList` (evaluated rows **and** the keys that
invalidate them) or an `ObservableValue` (a count plus its keys):

```python
@dataclass(frozen=True)
class ObservableList:
    model: type[Model]
    rows: tuple[Model, ...]
    keys: tuple[str, ...]
```

There is no public `QuerySet`: the filter and the key are written on adjacent
lines, so they cannot drift apart. Adding a new live list is deliberately a
two-line change — one key builder on the write side, one method here.

| Module | API |
|---|---|
| `sessions.py` | `root(archived=, project_id=)`, `children()`, `by_project()`, `by_pk()`, `active_subagent_count()` |
| `conversation.py` | `Message/Query/Response/TaskCall`: `by_session()`, `by_pk()`, `Response.by_query()` |
| `agents.py` | `AgentModel`/`SkillModel`: `root()`, `by_parent_project()`, `by_parent_agent()`, `by_parent_skill()`, `by_pk()`; version lists `by_agent()` / `by_skill()` |
| `structure.py` | `Project.root()`, `WorkspaceModel.root()` / `by_project()`, `ApiProvider.root()`, `AiModel.by_provider()`, `TerminalSession.by_session()` |
| `work.py` | `Cronjob`/`DataCollection`/`WorkItem` root and relation lists, `CollectionItem.by_collection()` |
| `registry.py` | `api_for(model)`; everything not listed is `ROW_ONLY` and observed by primary key |

`registry.py` also lists `ROW_ONLY` models explicitly. A coverage test asserts
that every concrete `server` model either has a domain API or is row-only, so
adding a model without deciding how the UI observes it fails CI.

A second test asserts the cross-side invariant: for a row in the state a list
filters on, **every key the list subscribes to is a key the writer publishes**
(`test_observable_queries.py`). That is the guard against a stale list.

## Redis layout

```
agentone:sse:watch:<client>   STRING  JSON array of keys   TTL 60s (heartbeat)
agentone:sse:keys:<key>       SET     client ids
agentone:sse:<client>         CHANNEL one per connected tab
agentone:sse:seen:<client>    STRING  reconnect marker     TTL 300s
```

* `register_client(client, keys)` replaces the watch set, adds/removes the
  reverse-index entries, and refreshes both TTLs.
* The SSE heartbeat calls `touch_client()` every 15 s.
* A hard-killed tab expires after `WATCH_TTL`; the next fan-out prunes its
  reverse-index entries (`SREM`) instead of publishing into the void.
* `reset_client()` removes the tab when its stream ends cleanly.

The stream carries **event names**, never HTML. A lost event costs exactly one
refetch, and a reconnect emits `reset`, which every live component also
triggers on (`sse:reset`).

## Browser side

`webui/static/webui/app.js` (with the WebSocket shim in `webui/static/webui/ws-events.js`
and the event socket consumer in `webui/core/events.py`):

1. Creates an id per loaded document and injects
   `sse-connect="…?client=<id>"` into `<body>` before htmx processes the page.
   That URL is `/app/ws/events/`; the shim turns it into a WebSocket while
   keeping htmx's `sse:` event names, so no component trigger changes.
   `sessionStorage` is deliberately not used: duplicated tabs copy it and would
   share one channel/watch set (closing one would unsubscribe the other).
   `hx-ext="sse"` lives on `<body>` too, so a boosted navigation (which only
   swaps `<body>`'s contents) keeps the same id and `EventSource`.
2. Collects the `sse:` tokens from every rendered `hx-trigger`/`sse-swap`,
   debounces a `POST /app/sse/watch`, and skips the request when the set has
   not changed.
3. Sends `If-None-Match` from `data-component-etag` on every component
   request, so unchanged components answer `204` and htmx keeps the DOM (and
   with it focus, scroll and open `<details>`).
4. Re-derives the watch set after every `htmx:afterSettle` and on
   `htmx:sseOpen`. A failed/rejected POST is never cached as synced (the server
   still holds the previous set); a periodic forced re-post (30 s and on tab
   visibility) heals registrations lost to a reconnect/cleanup race.
5. There is **no** "unsubscribe when an unmatched event arrives" fallback. The
   server fans out from its registry; a stale entry only costs a refetch until
   the next re-post prunes it. Clean stream shutdown removes the tab in
   `reset_client()` (skipped if a newer stream owns the channel); a hard-killed
   tab expires after `WATCH_TTL` and is pruned on the next fan-out.

## Tests

| File | What it pins |
|---|---|
| `server/tests/test_observables.py` | key builders, bare keys, old+new transitions, `on_commit`, client registry, fan-out isolation, dead-client pruning, `save/delete/atomic_update/publish_by_pk`, FSM helpers |
| `server/tests/test_observable_queries.py` | registry coverage, no queryset escape, every read key is published by the writer |
| `server/tests/test_events.py` | frame format, event-name parsing, client-id validation, `/app/sse/watch` payloads and auth |
| `server/tests/test_webui_components.py` | ETag/204, cache headers, immutable components, `render=full` vs `render=htmx`, preserved component wrappers/placeholders, section sidebar routes |
| `webui/tests.py` | full page/boosted shell contracts, fragment routes, chat rendering |

## Known limitations

- `publish_model_event` is synchronous per publish (one `SMEMBERS` per key,
  pipelined). Bursts of hundreds of keys would benefit from a single
  Lua/pipeline lookup; the current volume (a handful of keys per write) does
  not justify it.
- An immutable component (finished message, terminal response) is rendered
  once with `max-age=31536000, immutable` **only when its whole session is
  inactive**. A message inside an active session stays `no-cache` so an edit
  or a late part still shows up.
- No WebSocket bundling yet. If parallel HTTP/1.1 component loads become the
  bottleneck, the same key set can move to one WebSocket without touching the
  publish path.

## File index

- `runtime/observable_keys.py` — grammar, builders, `observable_keys()`
- `runtime/observable_queries/` — `base.py`, `sessions.py`, `conversation.py`,
  `agents.py`, `structure.py`, `work.py`, `registry.py`
- `server/models/observables.py` — `ObservableMixin`, client registry,
  `publish_model_event`, `_fan_out`
- `server/models/base_model.py` — `BaseModel(ObservableMixin, DirtyFieldsMixin)`
- `webui/events.py` — SSE stream + `/app/sse/watch`
- `webui/components.py` — component registry, ETag/cache policy
- `webui/static/webui/app.js` — client id, watch-set sync, ETag header
