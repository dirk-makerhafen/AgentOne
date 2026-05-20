# AgentOne — AGENTS.md

## Stack

- **Django** — models, views, admin, Channels WS, Celery async tasks
- **Redis** — Celery broker/backend, channel layer, cache (all `redis://localhost:6379/1`)
- **MySQL** — primary DB (`config/settings.py` line 27); `db.sqlite3` is gitignored and stale
- **Celery** — beat tick at 5s (`tasks.tick_scheduler`), 2min heartbeat poll
- **pyHtmlGui** — custom WebSocket UI framework at `ui/`; ASGI consumer `ui.consumer.PyHtmlGuiConsumer`

## Directory ownership

| Path | Role |
|---|---|
| `config/` | Django settings, ASGI/WSGI, Celery app, URL routes |
| `server/` | Core Django app: models, admin, Celery tasks, migrations |
| `registry/` | Agent registration, `@task`/`@tool`/`@command` decorators (legacy), `Subagent` classes |
| `runtime/` | Agent execution runtime, context manager, rate limiter |
| `tools/` | Legacy tool implementations (`primitives/`, `builtin_filesystem/`) |
| `launcher/` | Launcher service with client |
| `ui/` | Web UI (pyHtmlGui), templates, static files, panels |
| `old/` | Dead legacy code — do not touch |
| `.agentone/` | **Active tool/agent config** (see below) |

## Tool system

**New tools** (in `.agentone/scripts/`): plain Python functions returning `(bool, dict)`. Each group has a `tool.md` manifest mapping names to files/functions. The framework auto-extracts schema from signatures/docstrings. No `@tool()` decorator.

**Legacy tools** (in `tools/primitives/`, `tools/builtin_filesystem/`): use `@tool()` decorator from `registry.task_decorators`.

Tool groups (`.agentone/scripts/`):
- `execution/` — `python`, `shell`, `kill`
- `filesystem/read/` — `read`, `glob`, `grep`, `stat`
- `filesystem/write/` — `write`, `edit`, `multiedit`, `append`, `copy`, `move`, `mkdir`, `rm`
- `web/` — `webSearch`, `webFetch`
- `workspace/` — `diff`, `task`, `tree`

## Agent hierarchy

- Base: `.agentone/agents/baseagent/agent.md` — core tools + tasks, `schedulerStrategy: queue`, `reasoningEffort: high`
- Primary: `.agentone/agents/agentone/agent.md` — extends `baseagent`, adds all 20 tools, model `gemma4:26b`

Agent definitions use YAML frontmatter in `.md` files. Subagents use `Subagent`/`Subagents` from `registry.sub_agents`.

## Key commands

```bash
# Run dev server (Django)
python3 manage.py runserver

# Run Celery worker
python3 -m celery -A config worker -l INFO

# Run Celery beat scheduler (required for tasks)
python3 -m celery -A config beat -l INFO

# Run a single tool from CLI (tools have __main__ blocks)
python3 .agentone/scripts/workspace/tree.py --depth 2

# Tests
python3 -m pytest .agentone/scripts/ -v           # tool tests (73 total)

# Lint
python3 -m pylint config/ server/ registry/ tools/


# Django migrations
python3 manage.py makemigrations
python3 manage.py migrate
```

## Constraints & gotchas

- **Use `python3`**, not `python` — the repo explicitly requires `python3`.
- `.pylintrc` sets `max-line-length=200`, disables `C0114/C0115/C0116`, loads `pylint_django`.
- `config/settings.py` uses MySQL by default (requires local MySQL/MariaDB + `PyMySQL`). Fall back to SQLite by uncommenting lines 16–23 and commenting 24–34.
- `db.sqlite3` is in `.gitignore` — it's stale if present. Use migrations on a fresh DB.
- Celery beat must be running for scheduler tasks (5s tick, 2min heartbeat poll).
- Redis must be running at `localhost:6379` for the full stack (channels, cache, celery).
- `agentone_public.py` at repo root is a flat re-export of key symbols — not a module.
- `old/` directory is dead code; `registry/task_decorators.py` has commented-out hooks/chord/setup sections.
