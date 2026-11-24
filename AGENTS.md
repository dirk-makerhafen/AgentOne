# AgentOne — AGENTS.md

Quick reference for developers working on AgentOne. See also:
- [README.md](README.md) — project overview, features, quick start
- [docs/user-guide.md](docs/user-guide.md) — end-user guide for the UI
- [docs/architecture.md](docs/architecture.md) — system architecture, data flow, component interactions
- [docs/development.md](docs/development.md) — setup, coding conventions, how-to guides
- [docs/core-mechanisms.md](docs/core-mechanisms.md) — task dispatch pipeline, auto-await, renderer internals
- [docs/auto-title.md](docs/auto-title.md) — automatic chat naming, fork design, comparison with other harnesses
- [docs/ui-rewrite.md](docs/ui-rewrite.md) — server-rendered UI architecture (htmx, SSE, components), rationale and shipped design
- [docs/htmx-sse.md](docs/htmx-sse.md) — practical htmx/SSE component contract, pitfalls, and chat/UI rules
- [docs/ui-implementation-guide.md](docs/ui-implementation-guide.md) — normative how-to + agent checklist for htmx/SSE/observables elements
- [docs/deployment.md](docs/deployment.md) — production deployment, supervisor, nginx
- [docs/folders.md](docs/folders.md) — canonical filesystem layout (scopes, `var/`, install repos)
- [docs/manifest-format.md](docs/manifest-format.md) — YAML manifest format (agents, scripts, cron, streams, sets)
- [docs/models.md](docs/models.md) — model reference (all ~30 models including DataCollection)
- [docs/provider-catalog.md](docs/provider-catalog.md) — deterministic provider/model JSON generation from upstream catalogs (`registry/catalog/`, `manage.py refresh_catalog`)
- [docs/free-tier-verification/](docs/free-tier-verification/README.md) — one self-contained task file per free-tier verification step (plan batch, provider metadata, free-tier verification, audit, QA)
- [docs/terminals.md](docs/terminals.md) — persistent tmux terminals + external CLI agents (tools, allowlist, guardrails, UI tab)
- [docs/browser.md](docs/browser.md) — Camoufox browser capability (daemon, session/tab scope, approvals, config)
- [docs/self-improvement.md](docs/self-improvement.md) — reflection → playbook → capability/harness loop, `memoryPlaybook` injection

## Directory ownership

| Path | Role |
|---|---|
| `config/` | Django settings, ASGI/WSGI, Celery app, URL routes |
| `server/` | Core Django app: models (~30), admin, Celery tasks, migrations |
| `registry/` | YAML manifest loader, install repo management, upstream source sync; legacy decorators (dead) |
| `runtime/` | Agent/session/task runtime wrappers, state machines, rate limiter; `runtime/browser/` holds the Camoufox daemon + client; `runtime/workitems/` holds the WorkItem FSM + verifier |
| `launcher/` | Launcher service for remote agent management; supervises the browser daemon |
| `webui/` | Web UI: Django templates + htmx + SSE — views, components, sidebar, chat, settings, overlays |
| `old/` | Dead legacy code — do not touch |
| `.agentone/` | Active tool/agent config: YAML manifests, scripts, skills, streams, sets |

## Agent hierarchy

- **baseagent** (`.agentone/agents/baseagent/agent.md`): core tasks + `ping` command, queue strategy, medium reasoning
- **AgentOne** (`.agentone/agents/agentone/agent.md`): delegate-only master, workspace `~/.agentone`; tools `core/subagents/history/todo/workitems` plus its own agent-local `admin_tool` (single dispatcher: `scope`/`action` + `help`); subagents `general-chat`, `coding`, `researcher`, `planner`, `wiki`
- **general-chat** (`.agentone/agents/general-chat/agent.md`): conversational assistant, no writes/execution; delegates to `coding`/`researcher`/`planner`
- **coding** (`.agentone/agents/coding/agent.md`): implementation specialist (filesystem + execution + web); delegates to `researcher`/`planner`
- **internal framework agents** (`.agentone/agents/internal/`): only `approval_decider`, `work_verifier`, `memory-manage`, `reflection-mixin` and `compaction-mixin` remain; these are invoked by the framework, not delegated to. `memory-manage` is also user-facing as the Memory page's rightbar assistant, where it explains the memory tree and its tools. The former per-domain `*_assistant` / `*s_assistant` agents were consolidated into AgentOne — inspect framework state with its agent-local `admin_tool` and use `workitems.*` for durable work.
- **runtime collections** (`runtime/<domain>/`): singular + plural wrappers per item (`Skill`/`Skills(parent_agent=, parent_project=, parent_skill=, parent_workspace=)`, `Agent`/`Agents(...)`, `Project`/`Projects()`, `Session`/`Sessions(parent_project=, parent_session=)`, `Workspace`/`Workspaces(parent_project=, parent_workspace=)`, `WorkItem`/`Workitems(parent_project=, parent_workspace=)`, `Cron`/`Cronjobs(parent_project=, parent_workspace=)`); `all()` is scope-filtered, `root()` stays unscoped, `list_*()` returns wrapped singulars; each exposes its (now unified) assistant name + source dir via `ASSISTANT_NAMES` / `get_source_dir()` / `get_assistant_session()`; source dirs prefer the stored `manifest_dir` model field (Agent/Skill/Cronjob) or `agentone_dir` (Project/Workspace) with conventional-layout fallback
- **assistant scope invariant**: all rightbar assistant sessions bind one of three workspaces — the selected workspace, the project's primary workspace, or the single "AgentOne home" row at `agentone_home()` (`~/.agentone`); the old per-domain synthetic workspaces are gone. `Workspaces.assistant_workspace()` is the shared resolver used by every singular/plural wrapper and by `webui/core/assistants.py`. New assistant chats pin a one-time `SYSTEM_NOTICE` naming the page and intended work; `admin_tool` takes explicit `project_pk`/`project_name` or `workspace_pk`/`workspace_name` when the session binding is not the target. Workspace *ownership* (`parent_project`) and *path nesting* (`parent_workspace`) remain orthogonal.

Agent definitions use YAML frontmatter in `.md` files.

## Debug commands

| Command | Approval | Purpose |
|---|---|---|
| `/debug` | no | General debugging: `/debug ping`, `/debug approval` |
| `/test-approval` | **yes** | Tests the full guardrail/approval card UI flow |

## Setup

```bash
# Interactive setup — asks about DB type (SQLite/MySQL), Redis, TLS certs,
# runs migrations, and optionally creates a superuser
venv/bin/python manage.py server setup

# Start the server (Daphne + Celery worker + Celery beat)
venv/bin/python manage.py server run
```

See [docs/development.md](docs/development.md) for detailed setup instructions.

## Key commands

```bash
venv/bin/python manage.py server setup                 # initial configuration wizard
venv/bin/python manage.py server run                    # launch all server processes (Daphne + Celery)
venv/bin/python manage.py server update                 # git pull + pip install + migrate + reload
venv/bin/python manage.py runserver                     # dev server only (no Celery)
venv/bin/python -m celery -A config worker -l INFO      # worker
venv/bin/python -m celery -A config beat -l INFO        # beat (required for tasks)
venv/bin/python manage.py makemigrations && migrate     # DB schema
venv/bin/python manage.py merge_free_reviews --root .agentone   # validate cached reviews + write reviewed .agentone/free/
venv/bin/python -m pytest server/tests/ -v --reuse-db   # server tests (245+)
venv/bin/python -m pytest api/tests/ -v --reuse-db      # API tests (86)
venv/bin/python -m pytest .agentone/scripts/ -v         # tool tests (75)
venv/bin/python -m pytest server/tests/test_browser_*.py -v   # browser capability tests (74)
venv/bin/python -m pylint config/ server/ registry/     # lint
venv/bin/python .agentone/scripts/filesystem/read/tree.py --depth 2  # CLI tool
```

## Constraints & gotchas

- **Filesystem layout**: each scope (global, user, project, workspace) owns its manifests + a `var/` subtree (sessions/log/run/cache); machine-wide state lives under `~/.agentone/var/{install,browser}` and secrets under `~/.agentone/secrets/`. All path decisions go through `runtime/paths.py` (`ScopeRef`), never recompute `~/.agentone/...`. `venv/bin/python manage.py migrate_layout [--dry-run]` upgrades a pre-`var/` home.
- **Use the repo venv**: `venv/bin/python`, not bare `python`/`python3`. `manage.py` re-executes itself under the venv when invoked with another interpreter, so `python3 manage.py ...` is safe too; direct `pytest`/`celery`/`pylint` invocations are not.
- **Run tests with the repo venv** (`venv/bin/python -m pytest ...`, or with the venv activated) — system `python3` has the wrong Django version and DB tests error out.
- Session-private folders live in each scope's `var/sessions/<agent>/<pk>/` — global/user at `~/.agentone/var/sessions/<agent>/<pk>/` (`runtime/session_folder.py`, base overridable via `AGENTONE_SESSIONS_DIR` in `settings_local.py`); project/workspace at `<agentone dir>/var/sessions/<agent>/<pk>/`. Own folder is always guardrail-allowed, other sessions' folders always denied; folders with files are kept forever (incl. archived), while hard-deleted orphans and empty folders of ended (`is_active=False`) sessions are swept at startup and every ~10 min by `tick_scheduler._sweep_session_folders`.
- `.pylintrc`: `max-line-length=200`, disables `C0114/C0115/C0116`, loads `pylint_django`.
- `config/settings.py` defaults to SQLite. Override in `config/settings_local.py` for MySQL or custom config. File is gitignored. Run `venv/bin/python manage.py server setup` to generate one.
- `db.sqlite3` is gitignored and stale.
- Celery beat must be running (5s tick, 2min heartbeat).
- Redis must be running at `localhost:6379` (channels, cache, celery).
- **Bump `VERSION`** on release commits (repo root, currently `0.1.0`); do not create git release tags unless explicitly asked. See [docs/development.md](docs/development.md).
- `agentone_public.py` at repo root is a flat re-export — not a module.
- `old/` is dead code; `registry/task_decorators.py` has commented-out sections.
- UI tools in `.agentone/scripts/` must return `(bool, dict)` and be registered in a `scripts.md` manifest.
- Upstream sources (`.agentone/{skills}/skills.yaml`, `{agents}/sources.yaml`, `{scripts}/sources.yaml`) are merged via `~/.agentone/var/cache/upstream/` on every reload. Local files always override upstream.
- Data flows (`.agentone/streams/*.md`, `.agentone/sets/*.md`) replaced legacy named-pipe system. 
- Browser: one long-lived daemon (`runtime/browser/`) owns every Camoufox process, because the Celery pool is 5 prefork workers and per-worker globals would give 5 disconnected browsers. The daemon listens on loopback with a `0600` bearer token, reaps idle browsers, and persists Camoufox fingerprints so a reopened profile keeps its identity. One process per top-level chat session; child/subsession agents inherit the root's browser but only see tabs they opened. `browser` is `access: write`, and mutating actions (`open`/`navigate`/`click`/`type`/`back`/`evaluate`/`upload`/`download`) require approval — see [docs/browser.md](docs/browser.md).
- `_trigger_on_removed` in `tick_scheduler.py` (not reprocess_collection.py — it imports it) — the `source_calls` param must contain the AgentTaskCalls whose items were removed, not all source calls.
- Scheduler split: `tick_scheduler.py` runs the 10s tick (dispatch, propagate, release, the three work-item routines, plus idle compaction). One-minute sibling tasks live in their own modules: `cron_scheduler.py` (cron dispatch), `sleep_guard_scheduler.py` (keep-awake guard), `recovery_scheduler.py` (`tasks.tick_scheduler_recovery` — **currently DISABLED**: its `agentone-recovery-scheduler` beat entry is commented out in `config/settings.py:85`, so recovery does not run; `_cancel_duplicate_queries` lives in `startup_cleanup.py`), and `startup_cleanup.py` (one-time full cleanup, dispatched by `server run`).
- When writing tests for UI views (`webui/`), use `webui/tests.py` and `server/tests/test_webui_components.py`.

## Real-time UI events

`ObservableMixin.save()` / `delete()` / `atomic_update*()` publish an explicit
key list from `runtime/observable_keys.py` via
`publish_model_event(keys, instance, action)` (`server/models/observables.py`).
The event is deferred with `transaction.on_commit`, then fanned out to only the
tabs that registered one of those keys. Keys look like `Model:<pk>`,
`Model.<relation>:<id>`, `Model.root` or `Model.root@is_archived:false`; every
publisher also emits the bare model key (`Model`) for all-row lists, and a
filter transition publishes both the old and the new value.

Each tab receives those keys over **one WebSocket** (`/app/ws/events/`,
`EventsConsumer` in `webui/core/events.py`, routed in `config/asgi.py`).
`webui/static/webui/ws-events.js` supplies an EventSource-shaped
`htmx.createEventSource` so htmx's `sse:` triggers stay unchanged; watch sets
are still POSTed to `/app/sse/watch`. Do not switch this back to `EventSource`:
Chrome counts SSE streams against the six-per-origin HTTP/1.1 pool, which
starves new tabs once five or six are open. The legacy HTTP `/app/sse/` view is
kept only as a fallback.

Client registry (Redis): `agentone:sse:watch:<client>` (JSON key list, TTL 60s),
`agentone:sse:keys:<key>` (SET of client ids), `agentone:sse:<client>`
(channel), `agentone:sse:seen:<client>` (reconnect marker). Each browser tab
injects `?client=<id>` into the `<body>` SSE connection, derives its watch set
from the rendered `hx-trigger="sse:…"` attributes, and debounces
`POST /app/sse/watch` when the set changes. `webui/events.py` streams only that
tab's events; a reconnect emits `reset`, which every live component also listens
for.

Components are render-on-demand (`webui/components.py`): `GET /app/c/<name>[/<pk>]`
answers `private, no-cache` + ETag (→ `204` when unchanged), or
`max-age=31536000, immutable` for finished messages/terminal responses.
`render=full` (the default) inlines children; `render=htmx` emits
`hx-preserve` placeholders that load themselves, so a parent swap never
destroys an already-loaded child. See `docs/observables-migration.md` and
`docs/ui-rewrite.md` §5.6.1.

### Key UI files

| File | Role |
|---|---|
| `runtime/observable_keys.py` | write-side key builders + dispatch table |
| `runtime/observable_queries/` | read-side `ObservableList` / `ObservableValue` API (no queryset escapes) |
| `server/models/observables.py` | `ObservableMixin`, Redis client registry, `publish_model_event`, `_fan_out` |
| `webui/events.py` | per-tab SSE stream + `/app/sse/watch` |
| `webui/components.py` | component registry, ETag/cache policy, placeholders |
| `webui/static/webui/app.js` | client id, watch-set sync, `If-None-Match`, thread swaps |
| `webui/static/webui/ws-events.js` | EventSource-shaped WebSocket shim used by htmx's `sse` extension |

Skills provide specialized instructions and workflows for specific tasks.
Use the skill tool to load a skill when a task matches its description.
<available_skills>
  <skill>
    <name>customize-opencode</name>
    <description>Use ONLY when the user is editing or creating opencode's own configuration: opencode.json, opencode.jsonc, files under .opencode/, or files under ~/.config/opencode/. Also use when creating or fixing opencode agents, subagents, skills, plugins, MCP servers, or permission rules. Do not use for the user's own application code, or for any project that is not configuring opencode itself.</description>
    <location>file:///Users/Dirk/%3Cbuilt-in%3E</location>
  </skill>
</available_skills>
