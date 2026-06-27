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
- `_prev_collection_members` in `tick_scheduler.py` is a module-level dict — persists across tests in the same process, not thread-safe across Celery workers.
