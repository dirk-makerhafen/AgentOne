# UI implementation guide — htmx, SSE, observables, and the agent checklist

**Status:** normative for `webui/`. This is the “how to add or change one element” guide; the other docs explain history and internals.

**Read first:** [ui-rewrite.md](ui-rewrite.md) §5.6.1 (shipped architecture), [htmx-sse.md](htmx-sse.md) (contract and pitfalls), [observables-migration.md](observables-migration.md) (key grammar and Redis), and the “Real-time UI events” section of `AGENTS.md`.

> **Current paths.** The implementation lives in `webui/core/components.py`, `webui/core/events.py`, `runtime/observable_keys.py`, `runtime/observable_queries/`, `server/models/observables.py`, and `webui/static/webui/app.js`. Older docs sometimes say `webui/components.py` or `webui/events.py`; those modules moved under `webui/core/`.

---

## 0. The loop to keep in your head

```
ORM write
  └─ ObservableMixin.save/delete/atomic_update*()
       └─ publish_model_event(keys, instance, action)   [deferred with transaction.on_commit]
            └─ Redis: agentone:sse:keys:<key> → tab channels
                 └─ SSE frame: event: <key>           [name + small JSON hint, never HTML]
                      └─ htmx: hx-trigger="sse:<key> delay:150ms, …"
                           └─ GET /app/c/<name>[/<pk>][?params&render=htmx]
                                └─ ComponentData(context, keys, immutable)
                                     └─ ETag → 204 (unchanged) or HTML → outerHTML swap
                                          └─ app.js re-derives the tab's watch set from the new DOM
```

Two invariants make this safe:

1. **The URL is the source of truth.** Every server-derived element is re-fetchable from a URL. A missed SSE event costs one stale frame, not a corrupted page.
2. **SSE carries event names, not HTML.** The stream never renders templates and never decides which fragment to send. The component that changed refetches itself.

---

## 1. Decide what you are adding

| Kind | Use | Do not |
|---|---|---|
| Server-derived state (list row, card, header, panel body, sidebar) | A **component**: `ComponentSpec` + template + `/app/c/...` URL + `ComponentData` | Hand-roll `id`, `hx-get`, `hx-swap`, `hx-trigger`, or ETag handling in a template |
| A disclosure/detail fetched only when opened (query prompt, tool detail) | An **ad-hoc lazy fragment** with `hx-trigger="toggle once"` targeting an inner element | Let it become the only copy of state that a component wrapper should own |
| Genuinely interactive client state (composer draft, selection, drag-and-drop, terminal buffer) | A small **JS island** rooted in one element, configured with `data-*`, talking normal HTTP | Reach into other components' DOM or duplicate server state in JS |
| Purely static markup | A template partial included inside a component | Give it its own component URL just because it is a partial |

Every navigation target must also render as a real page (deep link, reload, new tab). Use `<a href>` plus `hx-get`/`hx-push-url`, not buttons that only work through htmx.

---

## 2. Component rules

### Registration and rendering

- Register a `ComponentSpec(name, template, build, ...)` in the owning feature module (for example `webui/features/chats/components.py`). `build(request, pk, params)` returns `ComponentData(context, keys=(), immutable=False, reset=True)`.
- Render it with `{% component "name" pk key=value %}`. The template tag chooses inline render or a self-loading placeholder from `component_inline`.
- A component template has **one root element** and renders identically inline and standalone. Do not maintain two rendering paths for the same thing.
- Use the generated wrapper from `webui/core/components.py`. It supplies the stable `id`, `data-component`, `hx-get`, `hx-swap="outerHTML"`, `hx-sync="this:replace"`, `hx-disinherit`, `hx-preserve`, ETag, and either SSE triggers or `hx-trigger="agentone:none"` for keyless wrappers. Never remove `hx-preserve` or `hx-disinherit`.

### Render modes

- `render=full` (default) renders the component **and its children** inline. Direct page loads and no-JS clients get a complete tree.
- `render=htmx` renders **placeholders** for children. Each placeholder self-loads with `hx-trigger="load, intersect once"` and keeps any landmark id it replaces (for example `<aside id="sidebar">`).
- For list/thread containers that would fan out many placeholder loads on a whole-container refetch (SSE reset/reconnect), return `inline_children=True` in the context. `chat-thread` does this.
- `ComponentData.reset=False` is only for leaf items that are fully rebuilt by a parent container's reset. Default to `True`.

### Keys and cache

- `keys` must cover **everything that affects the rendered output** — the row itself, its parent/list scope, and any related model whose write can change the markup. Missing keys are the usual cause of “it only updates after I click something”.
- `immutable=True` means no SSE trigger and `Cache-Control: private, max-age=31536000, immutable`. Only use it when the whole owning session/row is terminal. An active session's message stays `no-cache` so late parts and edits still appear.
- Live components are `private, no-cache` with an ETag. ETags mask CSRF tokens before hashing; do not add per-request nonces, timestamps, or unmasked tokens to component HTML. Unchanged refetches answer `204` and htmx keeps focus, scroll, and open `<details>`.
- Component responses vary on `Cookie`; page responses additionally vary on `HX-Request`.

### Data and rendering

- Prefer `runtime/observable_queries/` when adding a live list: it returns `ObservableList`/`ObservableValue` with the filter and its invalidation keys written next to each other. Do not let a raw `QuerySet` escape into a live view. Some older builders still use explicit f-string keys; if you touch one, keep the key list adjacent to the query it describes and make sure the cross-side invariant test still passes.
- **Check data provenance, not just the field name.** A row often stores a reference rather than the value: `QueryMessagePart` normally has `source_message_part` and **no own `content`**. Render through the model's public renderer (`to_content_blocks()` / `to_openai_message()`), and prefetch the source relations. This is exactly how an expanded query card ended up with `<div class="query-message-content"></div>` while the token count looked correct.
- Read paths must not write. Do not call something that estimates/persists tokens, bumps counters, or publishes an observable event just to render a fragment. Use read-only render helpers for display.
- Markdown from LLM/tool output is rendered server-side with `webui/core/markdown.py` (nh3-sanitised). Never inject raw model HTML or re-parse rendered HTML in the browser.
- Keep client-only state (active sidebar row, open panel tab, open `<details>`, composer draft) out of component URLs; forking the cache per click is a bug. `app.js` already records and restores open cards across thread swaps.

---

## 3. htmx rules

- Ordinary navigation: `<a href="..." hx-get="..." hx-push-url="true">`. Boosted responses use the minimal `webui/hx_base.html` shell; full loads use `webui/base.html`.
- Chat/volatile routes set `hx-history="false"` so back/forward refetches live content instead of restoring a stale snapshot.
- Component swaps are `outerHTML` on the wrapper. Do not use `hx-select`/`hx-target="main"` partial swaps for in-section sidebar or navigation flows; they bypass the boosted-shell/component contract.
- The keep-alive workaround in `app.js` is required: in `htmx:beforeSwap` it removes the swap target's `id` for preserved outerHTML swaps and restores it in `htmx:afterSwap` only if the node was not replaced. Without it, placeholder→loaded transitions and SSE self-refetches disappear. Do not remove it or rely on native preserve behaviour for self-swaps.
- Placeholders must keep `hx-trigger="load, intersect once"`, `hx-get`, `hx-preserve`, and their landmark id. `ensureComponentPlaceholders` is a fallback, not permission to break those attributes.
- A keyless/immutable wrapper gets the inert `hx-trigger="agentone:none"` from the core, because htmx otherwise defaults an `hx-get` element to `click` and a bubbled child click would replace it with stale state.
- CSRF is sent by the `htmx:configRequest` listener from the `<meta>` tag. Do not hand-roll token headers per form.
- Lazy disclosures use `hx-trigger="toggle once"` and target a specific inner detail element. They must be idempotent, re-fetchable, and survive a parent thread swap with their open state and loaded content intact.
- Static asset URLs use the `static_v` template tag's mtime `?v=` because whitenoise caches non-hashed asset names.

---

## 4. SSE rules

- The endpoint is `GET /app/sse/?client=<id>`; `app.js` injects the per-document id into `<body>` before htmx processes the page. One stream per tab, one watch set per tab.
- The watch set is derived from rendered `sse:` triggers and replaced by `debounced` `POST /app/sse/watch`. Never hardcode a client-side key list; a missed/failed POST must not be cached as synced.
- A failed POST leaves the tab subscribed to its previous view; periodic forced re-posts (30 s, tab visibility) heal races with reconnect cleanup. Do not add an “unsubscribe on unmatched event” fallback.
- Query-string `client` is an opaque channel address only. Never use it to widen a queryset — component URLs re-resolve their own scope on every request.
- The stream emits event names (keys) and a small JSON hint. It must never emit HTML. A reconnect emits `sse:reset`; every live component listens for it.
- Key grammar (from `runtime/observable_keys.py`):

  ```
  Model:<pk>                    one row
  Model.<relation>:<id>         FK-scoped list
  Model.root                    rows with no parent_*
  <key>@<field>:<value>         explicit filter variant
  ```

  Keys never contain `[`, `,`, or whitespace because htmx tokenises `hx-trigger` on those and the key is used verbatim as the SSE event name.
- Trigger shape is generated as `sse:<key> delay:150ms, …, sse:reset delay:150ms`. The delay coalesces bursts from parallel tool calls; `hx-sync="this:replace"` prevents overlapping refetches. If you hand-write a trigger for an ad-hoc fragment, keep both properties.
- Sub-call trees cross sessions. A write to a descendant `AgentTaskCall` publishes **every ancestor call key** as well as its own. A tool card subscribed to `AgentTaskCall:<pk>` must refresh when any descendant changes; `AgentTaskCall.session:<pk>` alone is not enough.
- Heartbeats run every 15 s; hard-killed tabs expire and are pruned on the next fan-out. Do not remove the heartbeat or the registry TTLs.

---

## 5. Observables rules

### Write side

- Let `ObservableMixin.save()` / `delete()` / `atomic_update*()` publish. Events are deferred with `transaction.on_commit`, so a refetch can never read pre-commit state.
- Key builders live in `runtime/observable_keys.py`, one explicit function per model. Add a key there, not an inline string in a template or view. Every publisher also emits the bare `Model` key for all-row lists.
- A filter transition publishes **both old and new values** (`is_archived:false` and `is_archived:true`, both project ids on a move). Without the previous value, a row can only ever be added to the new list and never removed from the old one.
- For internal re-saves that must not repaint the UI, pass `publish=False` (or use `publish_by_pk` deliberately). For an explicit event at a chosen call site — after a sequence of writes such as attaching parts — use the model's `publish()` shim; it still defers through `publish_model_event`.
- If you add a `server` model, decide in `runtime/observable_queries/` whether it has a domain API or is `ROW_ONLY`; the coverage test fails CI otherwise.

### Read side

- `ObservableList` and `ObservableValue` carry the evaluated rows/value **and** the keys that invalidate them. There is no public queryset to attach arbitrary filters to — adding a new live shape means adding a method, with the filter and key on adjacent lines.
- The cross-side test (`server/tests/test_observable_queries.py`) asserts that every key a read list subscribes to is a key the writer publishes. Keep it green; do not bypass it with ad-hoc keys that no writer emits.

---

## 6. Agent checklist

Copy this into a review pass. Every box should be checked with evidence (a code path, a test, or a browser observation), not with intent.

### A. Scope and data shape

- [ ] I identified the exact server state this element renders, **including indirect storage** (source FKs, content-addressed `GenericContent`, tool-call results, prefetched relations). I did not assume a field on the row is populated.
- [ ] I verified the sample markup with realistic data. A blank content `<div>` surrounded by correct metadata is a data-provenance bug, not a CSS bug.
- [ ] I classified the element as component / lazy fragment / island / static partial, and every server-derived state is re-fetchable from a URL.
- [ ] I listed every model and relation whose write can change this markup, not just the primary model.
- [ ] The render path is read-only: no `.save()`, no token estimation, no observable publish, no counter bump.

### B. Component contract

- [ ] `ComponentSpec` is registered with a template and `build()` returning `ComponentData` (not a bare context dict).
- [ ] Template has one root element and renders identically inline and standalone.
- [ ] Wrapper attributes come from `webui/core/components.py`; I did not hand-roll `id`, `hx-get`, `hx-swap`, `hx-sync`, `hx-disinherit`, or `hx-preserve`.
- [ ] `keys` covers all dependencies from A; `immutable` is true only for terminal rows/sessions; `reset=False` only if a parent fully rebuilds this leaf.
- [ ] List/thread containers set `inline_children=True` so reset does not fan out N placeholder loads.
- [ ] Placeholders keep `load, intersect once` and the landmark id they replace.
- [ ] ETag is stable across requests (no per-request nonce/token); unchanged render returns `204`.
- [ ] Client-only state is not in the component URL or params.

### C. htmx behaviour

- [ ] Navigation uses real `<a href>` + `hx-push-url`; chat routes keep `hx-history="false"`.
- [ ] Mutations are normal POSTs returning the next component state; CSRF comes from the global listener.
- [ ] No `hx-select`/`hx-target="main"` partial swap in a sidebar/navigation flow.
- [ ] Lazy disclosures use `toggle once`, target an inner detail element, are idempotent, and keep open state across a thread swap.
- [ ] The `app.js` preserve/self-swap workaround is intact; I did not remove IDs or bypass `beforeSwap`/`afterSwap`.
- [ ] Static URLs use `{% static_v %}`.

### D. SSE and observables

- [ ] Every dependency key comes from `runtime/observable_keys.py` grammar; no `[`, `,`, or whitespace in any key.
- [ ] Filter fields publish old **and** new values; FK moves publish old and new ids.
- [ ] Nested/ancestor `AgentTaskCall` keys are included where sub-calls can change the card.
- [ ] Live triggers include `delay:150ms` and `sse:reset`; keyless wrappers get `agentone:none`; immutable components have no trigger.
- [ ] Watch set is derived from the DOM by `app.js`; I did not add a hardcoded client key list or an unmatched-event fallback.
- [ ] Writes go through `ObservableMixin` with `on_commit`; internal re-saves use `publish=False`; nothing publishes from a GET.
- [ ] New models are covered by the read-side registry (domain API or `ROW_ONLY`) and the cross-side key test.

### E. Tests

- [ ] Component URL and id are deterministic; `render=full` and `render=htmx` are both exercised.
- [ ] HTML asserts **rendered content**, using the real data shape (source-backed parts, template rendering, tool calls), not just the presence of a wrapper class.
- [ ] ETag/204, cache headers, placeholders, and preserved wrappers are covered in `server/tests/test_webui_components.py`.
- [ ] Key coverage and cross-side invariant tests pass (`server/tests/test_observable_queries.py`).
- [ ] SSE frame/watch/auth tests pass if the transport or watch payload changed (`server/tests/test_events.py`).
- [ ] Full page/boosted shell contracts still pass in `webui/tests.py`.

Run:

```bash
venv/bin/python -m pytest webui/tests.py server/tests/test_webui_components.py \
  server/tests/test_observables.py server/tests/test_observable_queries.py \
  server/tests/test_events.py -q --reuse-db
```

### F. Browser verification (not optional for chat changes)

- [ ] Ctrl-R / reconnect produces `reset`, components refill, and open `<details>` stay open.
- [ ] Two tabs on the same session both update from one write.
- [ ] Boosted navigation, sidebar load/persistence, and back/forward restore work.
- [ ] Streaming turn updates message, query/tool cards, chat header/composer, and context ring.
- [ ] Lazy details (query prompt, tool detail) load on first expand and survive a thread swap.
- [ ] No console errors from htmx preserve, SSE source cleanup, or failed `/app/sse/watch` posts.

---

## 7. Red flags that mean “stop and re-check”

- A card shows tokens/timestamps/role but an empty content node → the builder read the wrong storage location.
- An element has `hx-get` but no `data-component` wrapper (or vice versa).
- A component declares keys that no writer publishes, or a writer publishes a key no component listens to.
- `immutable=True` on an active row, or `reset=False` on a component the parent does not rebuild.
- A GET/fragment builder calls `.save()` or publishes an event.
- A template hand-writes `hx-trigger` with a raw key containing a comma or space.
- Someone “fixes” a blank component by polling every 2 s instead of fixing keys or data provenance.

When in doubt, reproduce the exact fragment with `curl /app/c/<name>/<pk>?render=htmx` and the exact SSE event with the event name from `runtime/observable_keys.py`. If those two are right, the browser behaviour is almost always a wiring detail — not a reason to bypass the component contract.
