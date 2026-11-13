# UI rewrite proposal — from pyHtmlGui to server-rendered htmx + SSE

**Status:** The htmx cutover is implemented; soak testing and final sign-off remain. `webui/` (Django templates + htmx + SSE) serves `/`; the legacy pyHtmlGui UI is frozen at `/legacy/` for one release.
**Date:** 2026-11-11
**Decision:** replace pyHtmlGui with **Django templates + htmx + SSE**, keeping Django as the renderer.
**Related docs:** [`architecture.md`](architecture.md), [`core-mechanisms.md`](core-mechanisms.md).

> **Phases 0–5 (implementation complete; soak/sign-off remains).** `webui/`
> is a Django app mounted at `/app/` and `/` redirects to it, and `/app/` itself
> is login-protected by middleware. The old
> UI remains at `/legacy/`.
> It reuses `ui/static/css/main.css` for all design tokens and markup classes,
> adds a thin `webui/static/webui/app.css` layer, and ships:
> - `/app/` — dashboard (recent conversations + new chat)
> - `/app/chats` — conversation list (active/archived, pin/archive/restore)
> - `/app/chat/<id>` — server-rendered thread, query/response cards, tool cards,
>   thinking blocks, composer, and session panel with Details, Workspace,
>   Settings, Capabilities, Tasks, Calls, Subagents, Templates, Todos, and
>   Terminals tabs; todo auto/pause/clear and active-call cancellation controls
> - `/app/agents`, `/app/projects`, `/app/workspaces`, `/app/skills`,
>   `/app/cron`, `/app/collections`, `/app/workitems` — list + detail screens
>   with the key create/toggle/FSM actions
> - `/app/workitems/board` — kanban board with HTML5 drag-and-drop mapped to
>   the work-item FSM actions
> - `/app/insights[/<tab>]`, `/app/logs`, `/app/settings/<tab>` — insights,
>   log tail, and user settings
> - `/app/sse/?scope=session:<id>` and `?scope=global` — Redis pub/sub → SSE bridge
> - fragment endpoints for the thread, query detail, chat header/panel/tabs,
>   sidebar, terminal output, log tail, and kanban board
>
> Thinking, query and response cards are native `<details>` disclosures.  Query
> prompt context is fetched lazily on first expand (`hx-trigger="toggle once"`)
> so large prompts never inflate the initial page.  `app.js` records open cards
> before a thread swap and restores them in `htmx:afterSettle`, re-fetching any
> lazy detail, so a 1 Hz SSE refresh does not collapse what the reader opened.
> Static URLs carry an mtime `?v=` cache-buster (`static_v` tag) because
> whitenoise caches non-hashed asset names.
>
> Contextual panel parity is represented in the htmx detail screens: workspace
> Files/Usage; agent capabilities/sessions; project contents; skill
> relationships; cron history/cancellation; collection activity/derived flows;
> and provider/model facts, limits, and usage. Agent, project, workspace, skill,
> and cron details embed their scoped assistant chat in a right-side panel. The
> dashboard and Agents, Projects, Workspaces, Cron, and Work Items overviews
> also embed their corresponding collection assistant. The panel can switch
> among prior conversations, create a new scoped session, send messages, and
> open the selected thread in the full chat view. Work Items assistant chats
> retain the selected project scope (board and detail pages). The panel is a
> direct child of `.webui-entity-layout`, so it docks in the right column on
> wide screens and stacks below the content at `max-width: 900px`. These panels
> reuse the normal chat thread fragments and SSE refreshes rather than the
> legacy pyHtmlGui chat widgets.
>
> `server/models/observables.py` dual-publishes each observable key to
> `agentone:pubsub:<key>`. Fragments subscribe with `hx-trigger="sse:<key>"`.
> Sending is a normal POST; persistence stays async, so the POST response shows
> an optimistic bubble until the `Message.create` event refetches the thread.
> `nh3` sanitises markdown server-side; htmx 2.0.4, htmx-ext-sse 2.2.2 and
> Alpine 3.14.8 are vendored (Alpine not loaded yet). Deploy requires
> `collectstatic` so whitenoise serves `webui/static`.
>
> Implemented beyond the original Phase 2/4 checklists: slash-command palette
> (schema-driven form), inline message edit + rerun, clear conversation,
> JSON import, chat ToC / compaction-boundary jumps (`?around=`), sidebar
> rename/move/activity indicators, composer agent/model/reasoning/workspace
> overrides, image attachments (client-downscaled data URIs), message
> copy/TTS/fork, transcript/JSON export, provider smoke tests, session
> templates panel, sidebar chat search, the graphical context-usage ring, the
> live tmux terminal buffer, SSE reconnect banner, todo auto/pause/clear
> actions, and active task-call cancellation.
>
> Intentionally deferred (no legacy wiring to port): the toolsets picker (the
> legacy dropdown has no apply handler and the runtime exposes no toolset
> API), and the update/health banners (their legacy JS handlers were never
> wired). Agent and skill manifests can be created and edited from the new UI.


---

## 1. Executive summary

The current UI is a server-rendered DOM patcher built on a vendored fork of
pyHtmlGui. Every browser tab opens a WebSocket, the server builds a full Python
view tree for that tab, and every change re-renders a Jinja2 template string and
replaces a DOM subtree. Navigation is Python method calls on buttons, not URLs.

That architecture causes the three symptoms you named:

| Symptom | Root cause |
|---|---|
| A link cannot be opened in a new tab | Navigation is `<button onclick="pyview.open…">`, not `<a href>`. There is no URL for a tab; tab state lives only in `MainView.open_tabs` in server memory, per connection. A new tab would open the root page, not the thing you clicked. |
| Back/forward do nothing | The URL never changes. There is no `pushState`/`popstate` anywhere in `ui/`. |
| Agents struggle to understand it | 148 inline Jinja templates inside Python strings, a custom regex that rewrites `pyview.foo()` into `pyhtmlgui.call(<function-id>, …)`, weakrefs, observable lists, per-connection view trees, and no type contract. None of this is common knowledge. |

The recommendation is **not** to abandon server rendering. It is to keep Django
as the renderer and replace the broken parts around it:

- **htmx** for navigation and interaction — real `<a href>` links, real history,
  fragment swaps scoped to one component instead of a whole subtree.
- **SSE** (Server-Sent Events) for live updates — one async generator per
  connection, no per-tab Python object graph, no thread writing to a socket.
  The stream carries event *names*; components refetch their own fragment.
- **Django templates** as the component format — files on disk, not strings in
  Python, readable and greppable.
- A **small, explicit set of JS islands** (Alpine.js, no build step) for the few
  genuinely interactive widgets: composer, terminal, kanban drag-and-drop,
  charts.

This keeps the stack Python-only — no Node, no bundler, no lockfile — while
fixing every symptom you named. The current HTML markup and the 4,544-line CSS
design system carry over largely intact.

The backend barely changes. `server/models/observables.py` already derives the
exact event keys the UI needs and already publishes `(model, pk, action, data)`
on every ORM write. The only change is to publish those events to Redis pub/sub
so an SSE endpoint can consume them, instead of routing integer `function_id`s
into a per-connection weakref registry.

**Effort:** roughly 9–12 weeks for one senior dev, 6–8 weeks for two. The
estimate is dominated by parity breadth (149 view classes), not technology risk.

---

## 2. How the current UI actually works

### 2.1 Runtime path

```
Browser tab
  │  GET /                         Django view -> pyhtmlgui_page.html (one empty <body>)
  │  WS  /ws?token=<csrf>           PyHtmlGuiConsumer (ui/consumer.py)
  ▼
PyHtmlGui (global) ──► PyHtmlGuiInstance (one per tab, uuid key)
                         ├── UiAppView(app_instance, parent=instance)
                         │     ├── AppTitlebar
                         │     ├── RailView
                         │     ├── SidebarView (12 panels)
                         │     ├── MainView (open_tabs dict)
                         │     ├── RightPanel
                         │     └── overlays
                         ├── Jinja2 template cache
                         ├── function_id -> weakref registry
                         └── Redis subscription bookkeeping

ORM write (Celery worker or web process)
  └── Model.save() -> publish_model_event -> notify_observers -> notify()
        └── Redis HASH agentone:obs:<key>  (instance_key -> [function_id…])
        └── Redis LIST agentone:uiq:<instance_key>  (one JSON message)

Per-instance drain thread (ui/consumer.py:loop)
  └── BLPOP -> process_queue_messages -> function_id -> view callback
        └── view.update() -> render() -> Jinja2 -> HTML string
              └── WS {"name":"pyhtmlgui.replace_element","args":[uid, html]}
```

### 2.2 Key mechanics

- **`PyHtmlView.render()`** (`ui/lib/pyHtmlGui/pyhtmlgui/view/pyhtml_view.py`)
  returns a **complete wrapper element** `<div class="X" id="pv…">…</div>`.
- **`update()`** calls `pyhtmlgui.replace_element(uid, html)` in the browser,
  which does `parentNode.replaceChild(new_element, old_element)`. The entire
  subtree is destroyed and recreated.
- **Event binding** is done by `PyHtmlGuiInstance._prepare_template()`, a regex
  that finds `pyview.some_method(args)` in template text and rewrites it to
  `pyhtmlgui.call(<function-reference-id>, args)`. Python function references
  are held in a `WeakFunctionReferences` registry.
- **Lists** are `ObservableListView` / `QuerySetView`. They wrap each row in a
  view object, subscribe to Redis keys, and `insert_element` / `remove_element`
  individual rows.
- **Navigation** is `MainView.create_and_open_tab(view_class, subject)`. The
  open tabs are a plain dict in server memory, keyed by
  `f"{view_class.__name__}__{uid}"`.
- **Visibility** is manual: `set_visible()` attaches/detaches observers and
  creates/destroys row wrappers. Off-screen views do no work, but the tree is
  still built per connection.
- **Polling**: `PyHtmlGuiInstance._poll_loop` runs one thread per instance for
  `set_autoupdate_interval()` views (currently only the rate-limit card, 2s).

### 2.3 Size of the current surface

| Metric | Value |
|---|---|
| Python LOC in `ui/` (excluding vendored pyHtmlGui) | ~25,000 |
| View classes (`PyHtmlView`/`ModelView`/list views) | 149 |
| Inline `TEMPLATE_STR` blocks | 148 |
| `onclick=` handlers in templates | 467 |
| `pyview.` references | 1,988 |
| `<script>` blocks embedded in views | 38 |
| `call_javascript` / `eval_javascript` call sites | 26 |
| `orm_subscribe` call sites | 42 (only 12 distinct components) |
| `ui/static/css/main.css` | 4,544 lines |
| Vendored JS (jQuery, d3, diff2html, tex-mml, marked) | ~39,000 lines |
| DRF API LOC | ~6,900 (13 resources, 86 tests) |

The 25k Python LOC is **not** 25k LOC of product logic. A large share is
framework glue: weakrefs, visibility lifecycles, list-diff plumbing, HTML
strings, and manual subscription bookkeeping. That glue disappears in htmx,
because htmx has no object graph and no subscription registry — it just swaps
the HTML the server sends.

---

## 3. What is actually broken, and what isn't

This distinction matters, because the fix is narrower than "rewrite the UI".

**Not broken — keep it:**

- Server-side rendering. Rendering HTML in Django is not the problem. It is
  faster to build, easier to test, and easier for agents to read than a client
  component tree.
- The observable event model. `observable_keys()` already produces exactly the
  right subscription granularity.
- Celery, Redis, Daphne, DRF, the runtime wrappers, the domain model.
- The visual design. Skins, dark mode, spacing, and component look are fine.

**Broken — replace it:**

1. **No addressability.** A view is a Python object, not a URL. You cannot
   bookmark it, share it, open it in a new tab, restore it after a reload, or
   use browser history. Adding URLs means adding a router, which means the
   server no longer owns "which tab is open".
2. **Whole-subtree replacement.** `update()` destroys and recreates an entire
   subtree. That loses focus, text selection, scroll position, CSS transitions,
   and client-only state (open dropdown, textarea draft). It also re-parses and
   re-executes embedded `<script>` tags on every update. htmx swaps the *one*
   component that changed, by id.
3. **Per-connection Python object graph.** Each tab instantiates the whole view
   tree (149 classes) and holds it alive with weakrefs. Memory and GC cost scale
   with tabs, not with data. A restart or WS drop loses all UI state.
4. **Threading fragility.** Three threads write to one socket: the Channels
   consumer thread, the Redis drain thread, and the polling thread. The code
   already carries a long comment about Twisted's TLS BIO corruption when two
   frames interleave, and a `_send_lock` to serialize writes. SSE removes this:
   one async generator yields frames in order, by construction.
5. **Stringly-typed event plumbing.** Redis messages carry integer
   `function_id`s into a weakref registry. Only 12 components subscribe; the
   rest are stale until a user action or a manual refresh.
6. **Opaque to agents and new developers.** The `pyview.` → `pyhtmlgui.call`
   regex rewrite, weakrefs, observable visibility, and HTML-in-Python-strings
   are all project-specific knowledge.
7. **Security edges.** Server-driven `pyhtmlgui.eval_script` executes arbitrary
   JS via `new Function`. The CSRF token is passed in the WS query string.
   `marked.parse(el.innerHTML)` runs on model output and assigns back to
   `innerHTML` without sanitization — an XSS risk from LLM content.
8. **Asset pipeline.** No hashing, no tree-shaking; jQuery, d3, diff2html and
   tex-mml are loaded globally. The CSS is a single 4.5k-line file.

**Note on item 1 and htmx.** htmx is often described as "server rendering with
links". That is exactly the point: it keeps the part that works (Django renders
HTML) and drops the part that doesn't (a custom protocol for patching DOM by
object identity).

---

## 4. Options considered

| Option | Gets URLs/history | Reactive updates | Agent-friendliness | Effort | Verdict |
|---|---|---|---|---|---|
| **A. htmx + Django templates + SSE** | Yes (`hx-push-url`) | Yes (fragment swap) | Very high | Medium | **Chosen** |
| B. React + TS SPA + REST + WS events | Yes | Yes | High | High | Viable; better for heavy client interaction, worse for ops and markup reuse |
| C. Vue 3 + TS SPA | Yes | Yes | High | High | Same trade-off as B |
| D. Django Unicorn / LiveView clone | Partial | Yes | Low | Medium | Keeps a server-side component tree — the same class of problem |
| E. Patch pyHtmlGui (add URLs, anchors, history) | Partial | No | Low | Medium | Band-aid; leaves the object graph and full-subtree render |
| F. Svelte/SvelteKit | Yes | Yes | Medium | High | Fine technically; smaller ecosystem/training corpus |

### Why not React

React was the original recommendation and is still a good architecture. It was
overtaken by three facts specific to this codebase:

1. **The repo has no Node.** `python3 manage.py server run` is the whole
   production story. A Vite SPA adds `npm ci`, a lockfile, a build step in
   `server setup`/`server update`, and a CI job — permanent friction.
2. **The markup is reusable.** The 149 view classes are ordinary HTML with CSS
   classes wrapped in `TEMPLATE_STR`. That markup moves into template files
   almost verbatim. React re-authors all of it as JSX for no product gain.
3. **Update frequency is 1 Hz, not token-level.** `call_llm.py` calls
   `response.save()` every 1.0s (`SAVE_INTERVAL`). Fragment-swapping a message
   bubble once per second is perfectly adequate; you do not need a virtual DOM
   diffing deltas. This is the single fact that makes htmx the right call here.

React remains the better choice if the product later needs token-level
streaming, virtualized lists of thousands of rows, or heavy client-side state.
Nothing in this design prevents adding a React island for a specific screen.

---

## 5. Target architecture

### 5.1 Shape

```
┌─────────────────────────────────────────────────────────────────────┐
│ Browser                                                             │
│  htmx          navigation, forms, fragment swaps, history           │
│  SSE extension live updates (one stream per live region)            │
│  JS islands    composer · terminal · kanban DnD · charts            │
│  CSS           existing tokens/skins, split into files              │
└───────────────┬───────────────────────────────┬─────────────────────┘
                │ GET/POST (HTML fragments)      │ GET /events/* (SSE)
                │ session cookie + CSRF header   │ session cookie
┌───────────────▼───────────────────────────────▼─────────────────────┐
│ Django                                                              │
│  URLconf -> views -> templates (full pages and partials)            │
│  SSE views: async generator -> StreamingHttpResponse                │
│  DRF /api/v1/* retained for external + agent integrations           │
└───────────────┬─────────────────────────────────────────────────────┘
                │ Redis pub/sub  ui.obs.<key>
┌───────────────▼─────────────────────────────────────────────────────┐
│ Celery workers / ORM writes                                         │
│  publish_model_event -> notify_observers -> notify (unchanged API)  │
└─────────────────────────────────────────────────────────────────────┘
```

Key property: **the server holds no per-connection UI state.** A connection is
a Redis subscription plus a template renderer. Reloading the page, opening a
new tab, or restarting Daphne loses nothing that isn't in the URL or the
database.

### 5.2 Why server-rendered fragments

htmx asks one question per interaction: "which URL returns the HTML for the
thing that changed?" That is a question Django already answers well.

```html
<!-- a real link: middle-click and Cmd-click work, back/forward work -->
<a href="/chat/7" hx-get="/chat/7" hx-target="#main" hx-push-url="true">Chat</a>
```

Because it is a real `<a href>`, every route must also render as a standalone
full page. That requirement is a feature: deep links, reloads, and new tabs all
work by construction, not by remembering to restore state.

The same holds for mutations:

```html
<form hx-post="/chat/7/message" hx-target="#composer" hx-swap="outerHTML">
  …
</form>
```

No JSON serialization, no client cache, no invalidation logic. The server
returns the next state of the component.

### 5.3 The SSE event stream

One async generator per connection. No Channels consumer, no drain thread, no
polling thread, no per-tab Python view tree.

**The stream carries event *names*, not HTML.** This is the most important
design choice in the document, and it is deliberately different from the obvious
approach of pushing rendered fragments.

The SSE endpoint is a dumb, decoupled pipe. Each element that cares about a
change declares which event names it listens for and how to refetch itself:

```html
<!-- one message: refetches itself when this row changes -->
<article id="message-42"
         hx-get="/session/7/messages/42/"
         hx-trigger="sse:Message.pk:42"
         hx-swap="outerHTML">
  …rendered message…
</article>

<!-- the tail of the list: refetches when anything in this session is created -->
<div id="message-tail"
     hx-get="/session/7/messages/tail/"
     hx-trigger="sse:Message.session:7"
     hx-swap="outerHTML">
  …last N messages…
</div>
```

Event names are the existing observable keys, verbatim. `observables.py` already
computes `Message.pk:42` and `Message.session:7`, so no new naming scheme is
invented and templates can render the trigger attribute directly:

```django
hx-trigger="sse:{{ message.observable_key }}"
```

```python
# ui/events.py
async def events(request):
    keys = scoped_keys(request)                 # from ?scope=session:7
    async with redis_pubsub(keys) as pubsub:
        yield ": connected\n\n"
        async for channel, payload in pubsub.listen():
            name = channel.removeprefix("ui.obs.")
            yield sse(event=name, data=payload)   # event: Message.pk:42
```

```python
def sse(event, data, event_id=None):
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.extend(f"data: {line}" for line in data.splitlines())
    return "\n".join(lines) + "\n\n"
```

**Why names beat pushed HTML:**

1. **Correctness self-heals.** Every fragment is a URL. A missed event means a
   stale fragment until the next event or the next interaction — never a broken
   page. The SSE stream is an optimisation hint, never the only path to
   correctness.
2. **The stream never renders.** No template coupling in the event loop, no
   per-subscriber rendering cost, no "which fragment do I send for this event?"
   mapping to maintain. The SSE view is ~40 lines.
3. **Debuggable.** `curl -N /sse/?scope=session:7` shows the events; `curl
   /session/7/messages/42/` shows exactly what the browser will swap in. An
   agent can reproduce any UI state with two curl commands.
4. **Idempotent.** Replaying the same event is harmless: it refetches the same
   fragment from the database.

The cost is one extra round-trip per update. At 1 Hz that is irrelevant.

**Avoiding duplicate-append bugs.** Do not build "append the new message" logic.
Instead, two coarse listeners per chat: the tail container refetches on any
`Message.session:<id>` event, and each bubble refetches on its own
`Message.pk:<id>` event. Tail refetch is dedupe-free and handles create and
delete uniformly.

**Scoped subscription.** Do not accept arbitrary keys from the client. `/sse/`
takes a scope (`?scope=session:7`, `?scope=project:3`, `?scope=workitems`) and
resolves it server-side to the exact key set for that domain — the same
derivation the page uses. With no scope, subscribe to `ui.obs.*` and let the
htmx listeners filter; that is acceptable for a single-user deployment but
wasteful once several tabs are open.

**Reconnect.** `EventSource` reconnects automatically; the SSE extension
inherits it. On reconnect the page is already consistent because nothing was
held client-side, and the next event refreshes the stale fragment. Optionally
send an `id:` per event and support `Last-Event-ID` to replay — not needed for
parity.

**Coalescing.** `hx-trigger="sse:X delay:150ms"` collapses bursts, and
`hx-sync` prevents overlapping refetches of the same element. Streaming saves
arrive at 1 Hz, so coalescing matters mainly for bursts from parallel tool
calls.

**Heartbeat.** Emit `: ping` every 15–30 s so proxies and dead connections are
detected. Bound the per-connection queue; on overflow, drop events rather than
grow memory — the client self-heals on the next event.

**Connection budget.** One stream per tab, which stays well under the HTTP/1.1
six-connection limit; use HTTP/2 in nginx anyway.

**Verify in Phase 0:** htmx's `sse:` trigger parser must accept event names
containing dots and colons (`Message.pk:42`). This is the one assumption in the
design that needs an empirical check; if it fails, sanitise the name (e.g.
`Message-pk-42`) in a single helper used by both the server and the template
tag.

### 5.4 Fragment contract and DOM ids

This is the discipline that keeps htmx maintainable, and it is the one thing to
get right in Phase 1.

1. **Every swappable component is a template partial** that renders exactly one
   root element.
2. **Every swappable component has a deterministic id**, derived from its model
   and pk: `message-42`, `query-17`, `taskcall-9`, `session-row-7`,
   `workitem-31`.
3. **Partials render identically inline and standalone**, so the same file
   serves the full page and the fragment refetch endpoint.
4. **Every partial has a canonical fragment URL** (`/session/7/messages/42/`,
   `/workitems/31/`) and a model attribute exposing its observable key, so the
   template can emit its own `hx-get` and `hx-trigger` without custom logic.
5. **No component may depend on client state that isn't in the DOM.** If a
   dropdown is open, that is a DOM attribute, not a Python attribute.

Prefix partials with `_`. A partial served standalone by a fragment endpoint is
the same include used in the full page — there is no second rendering path. The
package and template layout is in §5.6.

### 5.5 Routing and history

URL is the source of truth. Every navigation is an `<a>`; Cmd/Ctrl-click and
middle-click work; back/forward work; deep links work.

| URL | Screen |
|---|---|
| `/` | Dashboard / recent chats |
| `/chat/:sessionId` | Chat workspace (messages, composer, cards) |
| `/chat/:sessionId?message=:pk` | Deep link to a message |
| `/agents` / `/agents/:id` | Agent list / detail |
| `/projects` / `/projects/:id` | Projects |
| `/workspaces` / `/workspaces/:id` | Workspaces |
| `/workitems?project=:id` | Kanban board |
| `/cron` / `/cron/:id` | Cron |
| `/dataflows` / `/dataflows/:id` | Collections |
| `/skills` / `/skills/:id` | Skills |
| `/insights` | Dashboards/analytics |
| `/logs?file=` | Logs |
| `/settings/:tab` | Settings |

Right-panel tabs become query params (`/chat/7?panel=tasks`), so they are
linkable too.

htmx specifics:

- `hx-boost="true"` on the app shell handles ordinary links and forms.
- `hx-history-elt="#app"` scopes the history snapshot.
- `hx-history="false"` on chat routes: force a refetch instead of restoring a
  stale DOM snapshot. Live content should never come from the history cache.
- `hx-push-url="true"` on every navigation.
- Filters and search live in the query string (`?agent=`, `?project=`,
  `?status=`) so views are shareable.

### 5.6 Templates and component structure

Move the 148 `TEMPLATE_STR` blocks into template files. The markup is reusable;
the `pyview.` calls are not.

**Template engine.** Django templates (DTL), decided: consistent with the rest
of the project, extremely well represented in training data, and adequate for
everything here.

**New app package.** Keep the old `ui/` untouched and mount the new app beside
it, so nothing collides during migration:

```
webui/
  urls.py                  # explicit URL table, appended to config/urls.py
  views/<domain>.py        # plain function views: chat, agents, cron, …
  events.py                # SSE endpoint + scoped key resolution
  templatetags/ui.py       # fragment_url / observable_key helpers
  templates/webui/
    shell/                 base.html, titlebar.html, rail.html, sidebar.html
    chat/                  page.html, _message.html, _query_card.html,
                           _tool_card.html, _composer.html, _banner.html
    workitems/             page.html, _card.html
```

One view module per domain, one template directory per domain, one partial per
swappable component.

**Component shape.** A list row is a partial, not a view class:

```django
{# ui/templates/chat/_message.html #}
<article class="message message--{{ message.role }}" id="message-{{ message.pk }}">
  <div class="message__body">{{ message.html_body|safe }}</div>
  <time datetime="{{ message.created_at|date:'c' }}">{{ message.created_at|timesince }}</time>
</article>
```

**Markdown is rendered server-side.** Replace `marked.parse(el.innerHTML)` with
a Python renderer plus sanitizer (e.g. `markdown-it-py` + `bleach`, or
`nh3`). This removes the XSS risk from LLM output and removes ~40 KB of vendored
JS.

**Icons** stay inline SVG, as today.

### 5.7 The JS islands — and only these

Everything else is HTML. These four are real modules with a documented contract,
not inline handlers. Islands use **Alpine.js** (~15 KB, declarative, no build
step) for local state, which removes most bespoke DOM plumbing while staying
readable:

| Island | Why it can't be HTML | Approach |
|---|---|---|
| **Composer** | autosize, send keys, drafts, attachments, command palette, model/profile/reasoning dropdowns, context ring | Alpine component. Config via `data-*` on the root. Drafts in `localStorage` keyed by session id. Send = `hx-post` returning the new message plus a cleared composer. |
| **Terminal** | xterm.js needs a real DOM buffer | `xterm.js` + a Channels WebSocket for input/output. Channels stays for this. |
| **Kanban DnD** | drag-and-drop is inherently client-side | `SortableJS` (~10 KB) or Alpine DnD. On drop, `POST` the new order; server re-renders the column. |
| **Charts** | canvas/SVG layout | Keep the existing static SVG/d3 rendering. No new chart dependency. |

Plus two tiny Alpine behaviours: **stick-to-bottom** on the message list, and a
**selection guard** that defers a bubble refetch while the user has an active
text selection inside it.

Rule: an island owns a single root element, reads configuration from `data-*`
attributes, and communicates by normal HTTP requests. It must not reach into
other components. If an island needs more than ~200 lines, that is a signal the
screen should be server-rendered instead.

### 5.8 Auth and security

This deployment is effectively **single-user**: there is no custom
`AUTH_USER_MODEL`, no `User` foreign key anywhere in `server/models/`, and most
`@login_required` decorators in `config/urls.py` are commented out. That lowers
the stakes, but it does not remove two real concerns: **scope isolation** (which
agent/project/workspace data a view may read) and **LLM output as an attack
surface**.

- Pages and fragments: Django session cookie + CSRF header. htmx sends
  `X-CSRFToken` via a `htmx:configRequest` listener reading a `<meta>` tag.
- SSE: session cookie, same-origin. `EventSource` sends cookies by default.
  This removes the `?token=<csrf>` handshake.
- `/sse/?scope=…` is resolved server-side against the same scoped querysets the
  pages use. A scope value that the caller cannot read returns 404, not a
  filtered stream. Never accept raw observable keys from the client.
- Add `@login_required` to every new view. It costs nothing and removes the
  current ambiguity. — **done via middleware**: `webui.middleware.
  WebuiLoginRequiredMiddleware` redirects anonymous `/app/` requests to the
  login page (`WEBUI_LOGIN_REQUIRED = True` by default).
- Remove `pyhtmlgui.eval_script` / `new Function` from the product path.
- Sanitize markdown server-side before it reaches the template.
- Keep CSP tight: no inline scripts once handlers move to files.

### 5.9 Build, assets, deployment

- **No bundler.** htmx, the SSE extension, SortableJS, and xterm are vendored
  as pinned files, like today's vendored JS but far fewer and smaller.
- Drop jQuery and jQuery-UI (the 467 `onclick` handlers become `hx-*`
  attributes). Keep d3 and diff2html where a feature still needs them.
- Static files continue through the existing static setup; `whitenoise` serves
  them.
- Optional: `esbuild` in one command for the JS islands if TypeScript is
  wanted. Not required for Phase 0.
- `python3 manage.py server run` remains the only production entry point.
- nginx: `proxy_buffering off; proxy_read_timeout 3600s; proxy_http_version 1.1;`
  on `/events/`, and HTTP/2 on the public listener.

### 5.10 Testing

This is a major win over a SPA: almost everything is testable with the Django
test client.

- **Views and fragments:** `assertContains(response, 'id="message-42"')` and
  `assertTemplateUsed`. No browser, no JS harness.
- **SSE:** call the async generator directly and assert the frames it yields.
- **Fragment contract:** a test per component that renders the partial both
  inline and standalone and asserts the root id and its `hx-get`/`hx-trigger`
  attributes, so id or trigger drift fails CI.
- **JS islands:** Vitest only for the composer's pure helpers (send-key
  parsing, autosize math). No DOM test harness for the rest.
- **E2E:** Playwright for the flows that justify it — open in new tab,
  back/forward, streaming a turn, approving a tool call.
- Existing DRF tests (86) and server tests (245+) keep running unchanged.

---

## 6. What we keep, what we delete

**Keep**

- Django, DRF, Celery, Redis, Channels, Daphne.
- `server/models/observables.py` event derivation (`observable_keys`,
  `publish_model_event`). It is good; it needs a pub/sub transport, not a
  rewrite.
- `runtime/` wrappers and the domain model. The UI rewrite does not touch agent
  execution.
- `api/` serializers/viewsets and their tests — still useful for external and
  agent integrations, and for the JS islands.
- The visual design: skins, dark mode, spacing, component look. Keep the CSS,
  split it into files, delete what is provably unused.
- The existing HTML markup, lifted into template files.
- Channels, specifically for the terminal WebSocket.

**Delete at cutover**

- `ui/lib/pyHtmlGui/` (vendored framework + examples).
- `ui/consumer.py` pyHtmlGui consumer and the per-instance drain thread.
- All `PyHtmlView`/`ModelView` subclasses and their `TEMPLATE_STR` blocks.
- `ui/lib/queryset_view.py`, `multi_queryset_view.py`, `status_badge.py`
  (logic moves into templates and template tags).
- The `pyview.` regex rewriter, weakref registries, `ObservableMappings`.
- jQuery/jQuery-UI, `marked.umd.js`, and any other vendored JS replaced by
  templates or small islands.
- The `?token=<csrf>` WS handshake.

**Freeze, don't delete immediately:** keep the old UI mounted at `/legacy`
during migration so users have a fallback and parity can be compared side by
side.

---

## 7. Migration plan

Strangler pattern. The new app lives at `/app` until parity, then takes `/`;
the old UI moves to `/legacy` and is deleted after a soak period.

### Phase 0 — Spike (2–4 days) — **done**

Prove the risky parts on one screen. Each step is independently verifiable
before the next one starts:

- **Event bridge first, no UI:** `observables.notify()` dual-publishes to Redis
  pub/sub; `curl -N /sse/?scope=session:7` streams `Message.pk:42` events while
  a Celery turn runs. This is testable from a terminal and de-risks the whole
  transport before a single template exists.
- Django URLconf + `base.html` shell; htmx, the SSE extension, and Alpine
  vendored.
- `/app/chat/:id` page view + per-message and message-tail fragment views.
- Message list rendered as partials; streaming message refetched by its own
  `sse:Message.pk:<id>` trigger.
- Real `<a>` navigation and browser history.
- Gate: send a message in `/app` and watch it appear live; open the same chat
  in a second tab and see both update; back/forward works; reload lands on the
  same chat; `curl` alone reproduces the same HTML the browser shows.

### Phase 1 — Foundation (1–1.5 weeks) — **done**

- App shell: titlebar, rail, sidebar tree, right panel, routing, theme/skins,
  toasts, error pages.
- Mount at `/app` behind a settings flag so the old UI stays the default until
  Phase 2 passes its gate.
- Template partial conventions + the id/URL contract + the tests that enforce
  it.
- SSE plumbing: scoped subscription resolution, heartbeat, slow-client drop,
  reconnect behaviour, `hx-sync` / `delay` coalescing.
- CSRF wiring for htmx, fragment error handling (`HX-Retarget`, `HX-Trigger`).
- `observables.notify()` gains pub/sub alongside the legacy RPUSH path.
- Create `docs/ui-htmx-progress.md`: a per-pane checklist of the 149 view
  classes, so parity is measurable rather than remembered.

### Phase 2 — Chat parity (3–4 weeks) — **done except the items marked below**

Highest value and highest risk, so do it first and completely:

- Message rendering: user/assistant/info, server-side markdown + sanitization,
  reasoning, parts (text/image), timestamps, copy/fork/TTS. — **done**
- Message list: render the 50 most recent, then "load older" via `hx-get`
  prepended to the list while preserving scroll offset. Cap the DOM and drop
  the far end for very long chats. — **done** (tail refetch + `?limit=`)
- Query cards, tool cards (args/result/approve/deny), queue card, approval
  card, guardrail card, clarify card, rate-limit card (now `hx-trigger="every 2s"`
  instead of a polling thread), banners. — **done**; the clarify card is dead
  legacy code and was not ported; update/health banners are deferred (their
  legacy JS handlers were never wired; the SSE reconnect banner is done).
- Composer island: autosize, send keys, drafts, attachments, command palette,
  model/profile/reasoning/toolsets/workspace dropdowns, context ring. —
  **done** except the toolsets picker (no runtime API); the slash-command
  palette, agent/profile picker and graphical context ring are done.
- Session sidebar: tree, search, pin/archive/rename/move, children/subagents,
  activity/approval indicators. — **done**
- Session settings, right-panel tabs, chat ToC and compaction boundaries. —
  **chat panel done** (details, workspace, settings, capabilities, tasks,
  calls, subagents, templates, todos, terminals + ToC/`?around=` + live
  terminal buffer). Contextual entity panels open as normal scoped chat
  sessions (a deliberate deferral from embedded chats). Final audit pass added
  the Settings identity card (rename, binding links, editable
  workspace/agent/model selects), subagent parent/turn/activity/model/message
  metadata with Close, terminal tmux liveness with Kill, colored call status
  badges with refresh, and the `/app/chats` "start a new chat" form
  (agent/workspace/name/description).
- Gate: a full agent turn, including tools and approvals, works identically in
  `/app`.

### Phase 3 — Management screens (2–3 weeks) — **implemented**

- Agents (overview, detail, versions, tools/tasks/skills/subagents, create);
  create/edit/delete go through manifest files + scope reload.
- Projects and skills, including their related entity/assistant panels;
  project edit (git URL, main workspace, manifest-in-workspace) and skill
  rename/delete are wired to the manifest layer.
- Workspaces (tree, Files browser, access editor, Usage, manager chat
  launch/history, create, edit, delete; storage switching and the access
  editor round-trip).
- Cron (overview, detail, history, create, edit, duplicate, delete, run-now;
  manifest writes, function targets, and per-job cancellation).
- Collections (detail, items, create, edit sources/processor/on-removed,
  delete, reprocess).
- Work items kanban (SortableJS island) with assignee/verification/
  actionable/terminal filters, create/edit/delete, FSM actions.
- Sidebar parity: recursive child/subagent session tree (active + recent
  inactive, capped depth), workspace colour dot, active-subagent count badge,
  streaming/approval indicators, pin/rename/move/archive menu, and the global
  project selector that scopes chat/agent/skill/cron/work-item lists. The
  selector stores its choice in the Django session (`sidebar_project_id`), so
  the filter survives navigation without being threaded through every link;
  `?project=<pk>` sets it and an empty value clears it. Sidebar panel
  variables are namespaced (`sidebar_sessions`, `sidebar_agents`,
  `sidebar_skills`, …) so page context cannot overwrite the sidebar's lists.
- Legacy contextual panel content and controls are exposed in detail screens.
  Entity assistant chats are embedded panels in the detail right column (the
  `webui/entities/_assistant_panel.html` shared partial), not separate chat
  pages, and the same collection assistant is docked on Work Item detail.
  Final audit pass added agent Extends/session count, project
  primary-workspace/session count, the workspace Manager-chat header action,
  the dashboard Projects card, and fixed the agent-detail panel being nested
  inside the content column.

### Phase 4 — Insights, logs, terminal, settings, overlays (1.5–2 weeks) — **done**

- Dashboards (overview stats + filterable task-call inspect table by agent,
  status, task and session), analytics (time range/provider/model filters over
  `Response` aggregates and the daily token series), provider/model facts,
  limits, usage, provider smoke test and per-model probing. — **done**;
  provider details also show retry-after/failure/built-in-key state and a Test
  button per model, and model details group provider variants by canonical id.
- Logs viewer (page + `hx-trigger="every 2s"` tail, or an SSE stream). — **done**
- Terminal (xterm.js island + Channels WebSocket). — **done without xterm.js**:
  the panel renders the live tmux buffer (`hx-trigger="load, every 2s"`), which
  matches the read-only need; interactive keystrokes stay with the agent tools.
- Settings (appearance, preferences, providers/keys, conversation, system). —
  **done**; providers support add/toggle/delete keys plus a cached smoke test,
  and conversation transcript/JSON export lives in the chat header.
- Onboarding, mobile overlay, dialogs. — **done** (mobile overlay + dialogs;
  no separate onboarding flow).
- Gate: feature parity is implemented; load/soak and final manual sign-off
  remain.

### Phase 5 — Cutover and cleanup (1 week) — **done (soak pending)**

- `/` redirects to `/app/` (login required); `/app/` itself is gated by
  `WebuiLoginRequiredMiddleware`. Old UI is frozen at `/legacy/`
  for one release. `collectstatic` + restart is required because whitenoise
  caches the file list at startup.
- Remove pyHtmlGui, dead JS/CSS, old tests; update docs (`README`,
  `docs/architecture.md`, `docs/core-mechanisms.md`, `ui/README.md`). — **not
  yet**: the legacy tree stays until the soak period ends.
- Load/soak test: many tabs, reconnect storms, long streaming turns, slow
  clients. — **pending**.
- Delete `/legacy` after a soak period. — **pending**.

### Rough effort

| Phase | One senior dev | Two devs |
|---|---|---|
| 0 Spike | 2–4 days | 1–2 days |
| 1 Foundation | 1–1.5 weeks | 1 week |
| 2 Chat parity | 3–4 weeks | 2–3 weeks |
| 3 Management | 2–3 weeks | 1.5–2 weeks |
| 4 Insights/etc. | 1.5–2 weeks | 1–1.5 weeks |
| 5 Cutover | 1 week | 0.5–1 week |
| **Total** | **~9–12 weeks** | **~6–8 weeks** |

Lower than the React estimate mainly because Phase 1 loses the API-gap
workstream, the TypeScript type pipeline, the client cache layer, and the
bundler/CI setup — and because management screens reuse markup instead of being
re-authored as components.

---

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Parity is wider than it looks | Schedule slip | Track the remaining parity items screen by screen; keep `/legacy` fallback |
| Stale fragments / duplicated rows | Wrong UI | Fragments are always refetchable by URL, so a missed event self-heals; refetch the list tail instead of appending; deterministic ids with a test per component |
| htmx `sse:` parser rejects dotted/colon event names | Transport broken | Verify in Phase 0; if it fails, sanitise names in one shared helper used by both server and template tag |
| Two-hop update latency (event → refetch) | Perceived lag | Acceptable at 1 Hz; `hx-sync` prevents overlapping refetches; coalesce with `delay:150ms` |
| Reconnect storms / many tabs | Server load | One stream per tab, bounded queues, backoff in the SSE extension |
| Slow clients / backpressure | Memory growth | Drop events above a cap rather than buffer; heartbeat detects dead connections |
| Proxy buffering breaks SSE | No live updates in prod | `proxy_buffering off`, `proxy_read_timeout`, HTTP/2; verify in staging behind the real nginx; document in `docs/deployment.md` |
| htmx SSE extension is young | Transport bug blocks launch | It is small and isolated; the fallback is `hx-trigger="every 10s"` on the same elements — a one-attribute change, not a rewrite |
| htmx history cache shows stale live content | Confusing back/forward | `hx-history="false"` on volatile routes; live content always refetches |
| Markup migration from Jinja strings | Tedious, error-prone | Mechanical port, one screen per PR, visual diff in review |
| Two paradigms (templates + islands) | Cognitive overhead | Keep islands to four, each with a documented `data-*` contract; everything else is HTML |
| Terminal/logs need streaming | Extra endpoint | Terminal keeps Channels WS; logs can poll with `hx-trigger` first |
| Scope/permission logic currently lives in views | Security bug if fragments bypass it | SSE and fragment views share the same scoped querysets as pages; tests per endpoint |
| `observables.notify()` becomes a hot path | Latency | Publish to pub/sub off the request path where possible; keep payloads small (ids, not full objects) |
| CSS is one 4.5k-line file | Maintenance | Split into files during port; delete unused rules with a coverage check |
| Agent/tool integrations depend on old UI classes | Breakage | Audit `ui` imports outside `ui/` before deleting; keep compatibility shims until cutover |

---

## 9. Why this is also the right move for agents

- **Standard stack.** Django templates, htmx, SSE, and plain HTML attributes are
  heavily represented in training data and documentation. There is no
  project-specific protocol to learn.
- **Curl-able.** Every screen and every fragment is a URL. An agent can
  `curl /chat/7` and see exactly what the browser receives. Debugging does not
  require a browser, a WebSocket, or a view tree.
- **No build step to get wrong.** An agent edits a template or a view and
  reloads. No bundler cache, no stale source map, no type-generation step.
- **Small blast radius.** A component change is one partial plus one view. It
  does not require understanding the visibility lifecycle, observer mappings,
  and function-id registry.
- **Testable without a browser.** `assertContains` covers most of the UI. The
  four JS islands are the only places that need Playwright.
- **Explicit contracts.** URLs, template partials, the `id` convention, and the
  `data-*` island contracts are all self-describing.
- **Shareable knowledge.** An agent can open a deep link to reproduce a bug.

---

## 10. Decisions

**Resolved**

1. **Approach:** htmx + Django templates + SSE, with four JS islands.
   Chosen over a React SPA for Python-only ops, markup reuse, and a 1 Hz update
   rate.
2. **CSS:** keep the existing design tokens and skins; split `main.css` into
   files during the port. No Tailwind migration.
3. **SSE wire format:** event names (observable keys), not pushed HTML.
   Components refetch their own fragment URL. Correctness self-heals; the
   stream never renders.
4. **Client state in islands:** Alpine.js, no build step.
5. **Template engine:** Django templates (DTL).
6. **First delivery:** chat parity plus the app shell and sidebar, mounted at
   `/app`. Management screens keep the old UI until Phase 3.
7. **Docs:** `ui-htmx-plan.md` is merged into this document and deleted. This
   file is the single authoritative plan.

**Still open (defaults recommended)**

8. **Cutover:** parallel `/app` with `/legacy` fallback, rather than a hard
   switch at the end.
9. **Streaming:** 1 Hz `Response.save()` events over SSE for parity, with
   token-level deltas as a later, separate project.

---

## 11. First concrete step

Build the Phase 0 spike:

- **Event bridge first:** `observables.notify()` dual-publishes to Redis pub/sub;
  `curl -N /sse/?scope=session:7` streams events while a Celery turn runs.
- Django `base.html` shell, htmx + SSE extension + Alpine vendored, `/app`
  URLconf behind a settings flag.
- `/app/chat/:sessionId` page with message partials, a minimal composer, and
  per-message + message-tail fragment views wired to `sse:` triggers.
- Real `<a>` links and working browser history.

That is a few days of work and answers the only real unknowns: htmx's handling
of dotted event names, SSE behaviour behind the real proxy, refetch cost per
event, and how much of the chat surface is straightforward template work versus
hidden coupling.
