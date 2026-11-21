# htmx + SSE UI: component rules and pitfalls

This is the practical contract for `webui/` (Django templates + htmx 2.0.11 + vendored htmx-ext-sse 2.2.4). Read [ui-rewrite.md](ui-rewrite.md) for architecture/rationale and [observables-migration.md](observables-migration.md) for observable keys. For a prescriptive how-to and the agent review checklist, use [ui-implementation-guide.md](ui-implementation-guide.md).

## Core model

- **Server-rendered components, cached per component.** Every server-derived UI element is a component with its own URL, ETag, and observable keys (`webui/core/components.py`, registry in feature modules). Component URLs: `/app/c/<name>` and `/app/c/<name>/<pk>`; section sidebars: `/app/<section>/sidebar`.
- **Two render modes.**
  - `render=full` (default, used for direct document loads): render the component and its children inline. `render_page()` sets `component_inline=True` for non-HX requests.
  - `render=htmx` (used by htmx/component refetches and boosted shells): render the component with **placeholders** for its children. Placeholders self-load (`hx-trigger="load, intersect once"`). `render_page()` sets `component_inline=False` for HX requests.
  - **Container opt-in:** a builder may return `inline_children=True` in its context to inline children even for `render=htmx`. Use this for list/thread containers (e.g. `chat-thread`) that would otherwise fan out N placeholder loads on a whole-container refetch such as SSE `reset` on reconnect/reload. The container response is larger, but the UI stays complete in one swap instead of appearing empty until children load.
- **One event socket per tab, event-name driven.** `layout/base.html` bootstraps `sse-connect="/app/ws/events/?client=<id>"` on `<body>`; `webui/static/webui/ws-events.js` turns that into a WebSocket (EventSource-shaped shim), and `app.js` syncs the tab’s watched key set to `POST /app/sse/watch`. Components refetch themselves on `hx-trigger="sse:<observable-key> delay:150ms, …, sse:reset delay:150ms"` (live components). Immutable components have no SSE trigger and long cache. WebSocket transport matters: Chrome counts `EventSource` streams against its six-per-origin HTTP/1.1 pool, so five or six tabs starve new document/component requests; WebSockets use a separate, much larger per-host pool.
- **Boosted navigation.** HX requests render with `layout/hx_base.html` (minimal `<html><head><title>…</title>{% block head %}</head><body>…</body></html>`) so htmx can swap `<body>` innerHTML and merge `<head>`; full loads use `layout/base.html`. Responses set `Vary: HX-Request`, `Cache-Control: private, no-cache`.

## Component contract (do not break)

- Component wrappers are emitted by `webui/core/components.py` with stable id `c-<name>-<pk>-<hash>`, `data-component`, `hx-get` to the component URL (`render=htmx`), `hx-swap="outerHTML"`, `hx-sync="this:replace"`, and `hx-preserve`.
- `hx-preserve` exists so a **parent** swap that re-emits a placeholder for an already-loaded child keeps the live child (htmx preserve pantry). It must not be removed from wrappers.
- Loaded/live wrappers carry SSE triggers + ETag; placeholders carry `hx-trigger="load, intersect once"`. ETags mask CSRF tokens before hashing. Unchanged refetches return `204`.

### Critical pitfall: preserve + self-targeted outerHTML swaps (htmx 2.0.11)

htmx 2.0.11’s preserve pass pantries any existing element whose id matches a preserved element in the incoming fragment. For a **self-targeted** outerHTML swap the target itself matches, so the target is pantried and the response is discarded or the element disappears. This breaks:

- placeholder → loaded transitions (initial component load), and
- SSE/reset self-refetches of already-loaded components.

**Workaround (required):** `webui/static/webui/app.js` removes the swap target’s `id` in `htmx:beforeSwap` for outerHTML swaps of preserved targets (descendants keep their ids, so parent-swap preservation still works) and restores it in `htmx:afterSwap` only if the original node remains connected (swap failed/cancelled). **Do not remove or bypass this workaround.** If you change swap behavior, ensure it stays compatible.

## SSE / observable keys

- Keys come from `runtime/observable_keys.py` and are published by `server/models/observables.py` / `publish_model_event`; `webui/core/events.py` fans out to watched clients.
- A component’s keys must cover **everything that affects its rendered content**. If a component renders state driven by task calls, session state, or responses (e.g. chat thread/cards, chat header busy/usage), include `AgentTaskCall.session:<pk>`, `SessionModel:<pk>`, `Response.session:<pk>` etc. as appropriate — missing keys mean the UI will not live-update.
- Sub-call trees cross sessions (a delegated sub-task lives in its own session). An `AgentTaskCall` write therefore publishes every ancestor call key (`AgentTaskCall:<ancestor_pk>`) as well as its own; a tool card subscribed to `AgentTaskCall:<pk>` refreshes when any descendant changes. Never rely on `AgentTaskCall.session:<pk>` alone for nested calls.
- The watch set is derived from the DOM and replaced on every sync (debounced after swaps, forced on reconnect/visibility/every 30 s). A failed POST must not be cached as synced, and `reset_client()` must not delete a registration that a replacement stream has already taken over — either case leaves a live tab subscribed to its previous view with no event-based fallback.
- `ComponentData.reset=False` is for leaf items fully rebuilt by a parent container’s reset; otherwise reset refetch is usually desired.

## Patterns and anti-patterns

- Prefer `{% component %}` + component endpoints for component-managed UI. Ad-hoc fragment endpoints that return raw templates (bypassing component wrapping/ETag/triggers) are fine only when intentionally targeting a specific inner element with its own refresh contract — do not mix them in ways that leave a component wrapper stale/conflicting.
- Do not use `hx-select`/`hx-target="main"` partial swaps for in-section sidebar/navigation flows that rely on the boosted shell/component contract; prefer plain boosted links for section navigation (see `ui-rewrite.md` / app decisions).
- Keep the boosted/HX shell minimal (`layout/hx_base.html`) — no doctype/base assets/SSE/body wiring there.
- `render=htmx` child placeholders must be loadable: `ensureComponentPlaceholders` in `app.js` provides fallback/retry for missed `load` wiring, but don’t break placeholder attrs (`hx-trigger="load, intersect once"`, `hx-get`, `hx-preserve`, outerHTML self-swap).
- `hx-history="false"` is used for chat routes to avoid stale restored DOM; `htmx:historyRestore` must reprocess and re-ensure placeholders (handled in `app.js`).
- `webui/static/webui/sse.js` is a local fork of htmx-ext-sse 2.2.4 with listener/source lifecycle fixes — reconcile carefully on upgrades. `webui/static/webui/ws-events.js` runs before it and supplies `htmx.createEventSource` as an EventSource-shaped WebSocket, so the extension and all `sse:` triggers stay unchanged.
- **Placeholder fan-out:** a container refetch that emits placeholders for many children (e.g. chat messages) causes N follow-up requests. On SSE reconnect/reset this can make the UI appear empty for a long time. Prefer `inline_children=True` for such containers, or avoid whole-container reset refetches when children can self-update. Ensure `ensureComponentPlaceholders` runs on the live DOM after swaps (not a detached `evt.target`).
- **Tool cards:** `AgentTaskCall:<pk>` is published for every descendant write. Do not put that key on `chat-message` (it would replace the whole message on every sub-task tick). The card's summary (`chat-tool-summary`) and sub-task flow (`chat-tool-subcalls`) own it instead; the lazy detail fragment stays keyed on the same event but normally answers `204`, so argument/result panes are not swapped. The flow component uses a `full` param for "show finished" — keep the "Show N finished" button targeted at the component wrapper, not at `.webui-tool-detail`.
- **Nested live components:** component wrappers set `hx-target="this"` in addition to `hx-disinherit`. htmx checks `hx-disinherit` on the ancestor that owns the inherited attribute, so a wrapper inside an element with `hx-target` (the tool card detail pane, a composer form, ...) would otherwise send its SSE refetch to that ancestor and throw `htmx:targetError`. Never move a live component under such an ancestor without keeping an explicit self-target.
- **Lazy placeholders and ETags:** `ensureComponentPlaceholders` must not send a second `load` for a placeholder htmx already initialized; the duplicate outerHTML swap pantries the freshly loaded component. A self-loading placeholder must also bypass the path-keyed ad-hoc fragment ETag cache in `app.js`: reusing the ETag of an earlier loaded component makes the empty placeholder answer `204` and never render when the parent detail is re-opened. Loaded component wrappers keep their own `data-component-etag`, so SSE refreshes still skip unchanged HTML. Conditional GETs from `app.js` carry `X-AgentOne-ETag: 1`; the server ignores a bare `If-None-Match` so a browser's own revalidation cannot return `204` and leave a lazily loaded detail pane empty after a page reload. The same path-cache rule applies to an unrendered tool-detail pane: while `.webui-detail-loading` is still present, `app.js` must send no ETag at all, otherwise clicking a newly rendered card can reuse the ETag of a previous detail load and stay forever on "Loading…". The cache is used again after the first successful render, so SSE refreshes still return `204` for unchanged detail HTML.

## When changing chat/UI

- Update component builders’ keys when rendered data dependencies change.
- Run: `PYTHONPATH=. venv/bin/python -m pytest webui/tests.py server/tests/test_webui_components.py -q --reuse-db`
- Browser-verify: boosted navigation, sidebar load/persistence, Ctrl-R + SSE reset/reconnect, chat thread live updates (messages, approvals/cards, header/composer), and back/forward restore.
