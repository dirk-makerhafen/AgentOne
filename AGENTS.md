# AgentOne — AGENTS.md

Quick reference for developers working on AgentOne. See also:
- [README.md](README.md) — project overview, features, quick start
- [docs/user-guide.md](docs/user-guide.md) — end-user guide for the UI
- [docs/architecture.md](docs/architecture.md) — system architecture, data flow, component interactions
- [docs/development.md](docs/development.md) — setup, coding conventions, how-to guides
- [docs/core-mechanisms.md](docs/core-mechanisms.md) — task dispatch pipeline, auto-await, renderer internals
- [docs/deployment.md](docs/deployment.md) — production deployment, supervisor, nginx
- [docs/manifest-format.md](docs/manifest-format.md) — YAML manifest format (agents, scripts, cron, streams, sets)
- [docs/models.md](docs/models.md) — model reference (all ~30 models including DataCollection)

## Directory ownership

| Path | Role |
|---|---|
| `config/` | Django settings, ASGI/WSGI, Celery app, URL routes |
| `server/` | Core Django app: models (~30), admin, Celery tasks, migrations |
| `registry/` | YAML manifest loader, install repo management, upstream source sync; legacy decorators (dead) |
| `runtime/` | Agent/session/task runtime wrappers, state machines, rate limiter |
| `launcher/` | Launcher service for remote agent management |
| `ui/` | Web UI (pyHtmlGui): views, sidebar, chat, settings, overlays |
| `old/` | Dead legacy code — do not touch |
| `.agentone/` | Active tool/agent config: YAML manifests, scripts, skills, streams, sets |

## Agent hierarchy

- **baseagent** (`.agentone/agents/baseagent/agent.md`): core tasks + `ping` command, queue strategy, medium reasoning
- **AgentOne** (`.agentone/agents/agentone/agent.md`): extends baseagent, all 20 tool groups

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
python3 manage.py server setup

# Start the server (Daphne + Celery worker + Celery beat)
python3 manage.py server run
```

See [docs/development.md](docs/development.md) for detailed setup instructions.

## Key commands

```bash
python3 manage.py server setup                 # initial configuration wizard
python3 manage.py server run                    # launch all server processes (Daphne + Celery)
python3 manage.py server update                 # git pull + pip install + migrate + reload
python3 manage.py runserver                     # dev server only (no Celery)
python3 -m celery -A config worker -l INFO      # worker
python3 -m celery -A config beat -l INFO        # beat (required for tasks)
python3 manage.py makemigrations && migrate     # DB schema
python3 -m pytest server/tests/ -v --reuse-db   # server tests (245+)
python3 -m pytest api/tests/ -v --reuse-db      # API tests (86)
python3 -m pytest .agentone/scripts/ -v         # tool tests (75)
python3 -m pylint config/ server/ registry/     # lint
python3 .agentone/scripts/filesystem/read/tree.py --depth 2  # CLI tool
```

## Constraints & gotchas

- **Use `python3`**, not `python`.
- `.pylintrc`: `max-line-length=200`, disables `C0114/C0115/C0116`, loads `pylint_django`.
- `config/settings.py` defaults to SQLite. Override in `config/settings_local.py` for MySQL or custom config. File is gitignored. Run `python3 manage.py server setup` to generate one.
- `db.sqlite3` is gitignored and stale.
- Celery beat must be running (5s tick, 2min heartbeat).
- Redis must be running at `localhost:6379` (channels, cache, celery).
- `agentone_public.py` at repo root is a flat re-export — not a module.
- `old/` is dead code; `registry/task_decorators.py` has commented-out sections.
- UI tools in `.agentone/scripts/` must return `(bool, dict)` and be registered in a `scripts.md` manifest.
- Upstream sources (`.agentone/{skills}/skills.yaml`, `{agents}/sources.yaml`, `{scripts}/sources.yaml`) are merged via `~/.agentone/upstream/` on every reload. Local files always override upstream.
- Data flows (`.agentone/streams/*.md`, `.agentone/sets/*.md`) replaced legacy named-pipe system.
- `_trigger_on_removed` in `tick_scheduler.py` (not reprocess_collection.py — it imports it) — the `source_calls` param must contain the AgentTaskCalls whose items were removed, not all source calls.
- Scheduler split: `tick_scheduler.py` runs the 10s tick (dispatch, propagate, release, cron); `recovery_scheduler.py` runs the 60s recovery pass (`tasks.tick_scheduler_recovery`) and one-time `tasks.startup_cleanup` (dispatched by `server run`).
- When writing tests for UI views (`ui/`), call `messages_view.set_visible(True)` in setUp to activate ObservableListView observer callbacks before exercising append/insert.

## Real-time UI events

The system uses `publish_model_event(instance, action)` in Celery tasks to push model changes to the browser via WebSocket:

| Model | Action | Celery file | Purpose |
|---|---|---|---|
| `Message` | `create` | `ingest_user_message.py`, `ingest_assistant_message.py`, `ingest_subagent_result.py` | Add new messages to chat without page reload |
| `Query` | `create` | `build_llm_context.py` | Insert query-card after trigger_message |
| `Query` | `update` | `call_llm.py` (after each status transition) | Re-render query-card status |

### Key UI callback files

| File | Role |
|---|---|
| `ui/main/chat/messages/messages.py` | `_on_message_created`, `_on_query_created`, `_on_query_updated` |
| `ui/lib/pyHtmlGui/pyhtmlgui/view/observable_list_view.py` | `set_visible` snapshot fix, dedup guard in `_on_subject_updated` |
| `ui/model_observer.py` | `unwatch_filter` for subscription cleanup on tab re-open |
| `runtime/events.py` | `publish_model_event`, `_extract_filter_context` |

Skills provide specialized instructions and workflows for specific tasks.
Use the skill tool to load a skill when a task matches its description.
<available_skills>
  <skill>
    <name>customize-opencode</name>
    <description>Use ONLY when the user is editing or creating opencode's own configuration: opencode.json, opencode.jsonc, files under .opencode/, or files under ~/.config/opencode/. Also use when creating or fixing opencode agents, subagents, skills, plugins, MCP servers, or permission rules. Do not use for the user's own application code, or for any project that is not configuring opencode itself.</description>
    <location>file:///Users/Dirk/%3Cbuilt-in%3E</location>
  </skill>
</available_skills>
