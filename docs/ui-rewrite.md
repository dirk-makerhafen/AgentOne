# UI rewrite — shipped design (webui)

**Status:** Implemented. The legacy pyHtmlGui UI has been removed. The only UI is `webui/` (Django templates + htmx + SSE), mounted at `/app/` (with `/` redirecting to it). Protected by `WebuiLoginRequiredMiddleware` by default.

**Related docs (source of truth):**
- [`observables-migration.md`](observables-migration.md) — observable keys, event fan-out, component caching/ETags, placeholder loading
- [`htmx-sse.md`](htmx-sse.md) — practical htmx/SSE rules, pitfalls, and component contracts
- [`ui-implementation-guide.md`](ui-implementation-guide.md) — normative how-to + checklist for `webui/` changes
- [`architecture.md`](architecture.md) — system overview
- [`core-mechanisms.md`](core-mechanisms.md) — task dispatch/auto-await context (UI section points here)

## What ships

- **Server-rendered pages and fragments** under `/app/` using Django templates + htmx 2.x.
- **Per-tab event socket:** `ws(s) /app/ws/events/` (see `webui/core/events.py`, `webui/static/webui/ws-events.js`). The client syncs watched observable keys via `POST /app/sse/watch`. Events carry key names/hints; components refetch their own fragment URLs.
- **Component system:** `webui/core/components.py` registers cacheable components (two render modes: `full` for document loads, `htmx` for fragment refetches with placeholders). Live components use `Cache-Control: private, no-cache` + ETag (`204` when unchanged); immutable components can be cached long-term.
- **Chat:** server-rendered thread, composer, panels (details/workspace/settings/capabilities/tasks/calls/subagents/templates/todos/terminals), SSE-driven refreshes; markdown sanitized server-side (`nh3`).
- **Management areas:** agents, projects, workspaces, skills, cron, collections, workitems (including board), insights, logs, settings — rendered as `webui` pages/components.
- **Assets:** vendored JS/CSS as in repo; `collectstatic` required for production (Whitenoise).

## Key implementation notes (non-obvious)

- htmx 2 preserve behavior can interfere with self-swaps of preserved targets; `webui/static/webui/app.js` contains a workaround in `htmx:beforeSwap`/`htmx:afterSwap`. Do not remove it without understanding the pitfall described in [`htmx-sse.md`](htmx-sse.md) and [`observables-migration.md`](observables-migration.md).
- `render_page()` uses boosted/base templates depending on `HX-Request`; chat pages typically opt out of htmx history caching where noted in code.
- Terminal/log streaming remains special-cased where needed (Channels/WebSocket behavior is documented in feature code and related docs).

## Removed

The former pyHtmlGui UI (`ui/`, `ui/lib/pyHtmlGui/`, `ui/consumer.py`, the old per-connection view tree, and related assets) was removed after the cutover. There is no `/legacy` route.

## If you need the old rationale

The historical analysis and migration narrative lived here previously; for current behavior refer to the related docs listed above. Git history preserves the prior version of this file if you ever need to review the old proposal text.
