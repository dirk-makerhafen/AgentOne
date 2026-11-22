# AgentOne

AgentOne is a Django-based autonomous agent framework with real-time Web UI, scheduled task execution, and a plugin-based tool system. It manages multiple AI agents with versioned configurations, tools, skills, and session state — all accessible through a browser-based chat interface.

## Features

- **Multi-agent runtime** — Run multiple agents with independent configurations, models, and tool sets, each with version-pinned agent definitions
- **Real-time server-rendered UI** — Django templates + htmx + SSE deliver independently cached live fragments without a Node build step or a page reload
- **Versioned everything** — Agents, tools, sessions, and settings are immutable once created; changes produce new versions with full history
- **Plugin tool system** — Tools are plain Python functions in YAML-defined groups with auto-extracted JSON schemas — no decorators
- **Celery task pipeline** — Asynchronous task dispatch with scheduling (5s tick, 2min heartbeat), state machine execution, and dependency resolution via M2M references
- **Subagent delegation** — Agents can delegate tasks with `delegate_task`/`start_subsession`/`spawn_subtask`, with automatic await and result delivery
- **Data flows (streams / ordered sets)** — Agents produce data into append-only streams or mutable ordered sets, which cascade to derived flows via propagation. Replaces legacy named pipes.
- **Project organization** — Agents, skills, and sessions can be grouped into projects with filtering across the sidebar
- **Rate limiting** — Three-tier rate limiting (provider → model → API key) with per-minute/per-day token and request limits
- **Multi-skin UI** — 7 built-in color skins (default gold, ares red, mono gray, slate, poseidon ocean, sisyphus purple, charizard orange) with light/dark mode
- **Safety guardrails** — Automatic pre-scanning of shell and Python commands via sh-guard and bandit, with human-in-the-loop approval for risky operations
- **Tool approval** — Optional human-in-the-loop approval for tool execution with inline consent cards
- **i18n-ready** — All UI text uses `data-i18n` attributes; JavaScript-based localization framework is stubbed and ready

## Quick start

One-line installer (clones the repo, creates `venv/`, installs dependencies,
runs the interactive setup, migrates, collects static files and reloads
manifests). It is a single standard-library Python script, so it works on
Linux, macOS and Windows — no shell or extra packages needed:

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python3 -
```

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python -
```

From an existing checkout: `python3 install.py --dir /srv/AgentOne --branch main`
(or `python install.py ...` on Windows). Useful flags: `--skip-setup`,
`--with-browser`. The old `install.sh` still works as a thin shim that downloads
and runs `install.py`, so existing `curl … install.sh | bash` links keep working.

Manual install:

```bash
# Prerequisites: Python 3.10+, git, Redis
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt

# Interactive setup — database, Redis, TLS certificate
venv/bin/python manage.py server setup

venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic
venv/bin/python manage.py reload_all

# Run (starts Daphne + Celery worker + Celery beat + browser daemon)
venv/bin/python manage.py server run
```

Activating the venv is optional: `manage.py` re-runs itself with `venv/bin/python`
if you invoke it with a different interpreter. The same applies to every child
process (Daphne, Celery, browser daemon) and to installed services.

Open the address printed by setup (default `https://localhost:7999`).

### Updating

```bash
venv/bin/python manage.py server update --check   # show versions / update availability
venv/bin/python manage.py server update           # full update
venv/bin/python manage.py server update --no-restart
```

The full update pulls with `--ff-only`, installs dependencies, runs `migrate`
and `collectstatic`, reloads manifests, and schedules a service restart. It
refuses to run on a dirty worktree unless `--allow-dirty` is passed.

Staff users can also use **Settings → System → Update AgentOne** in the UI.
It queues the same pipeline as a Celery task and streams its log into the panel.
The running version/commit is shown there and in `GET /api/v1/health/`.

If the web/Celery user cannot restart the service directly, set
`AGENTONE_RESTART_COMMAND` in `config/settings_local.py`, for example:

```python
AGENTONE_RESTART_COMMAND = ["sudo", "-n", "supervisorctl", "restart", "agentone-server"]
```

On Windows, an `agentone_server` service installed by `server service install`
is detected automatically and restarted with a detached PowerShell helper
(stop → wait for `STOPPED` → start). The service account needs rights to stop
and start services; otherwise set `AGENTONE_RESTART_COMMAND` explicitly.

### Windows support status

Native Windows (not WSL) runs the server, UI, Celery tasks, browser tools and
ad-hoc flows, with these caveats:

- **Redis is required** (Celery broker, Channels layer, cache). There is no
  fallback — install a native Windows Redis build or use WSL.
- **Terminals need tmux**, which is POSIX-only. `terminal_*` tools are
  unavailable; the UI still lists sessions from the database.
- **Celery uses `--pool threads`** by default on Windows (prefork is not
  supported). Override with `AGENTONE_CELERY_POOL` and
  `AGENTONE_CELERY_CONCURRENCY` in `config/settings_local.py`.
- **Service installs** use `sc.exe` (`server service install`, run as admin).
  `server run` chdirs to the checkout and prepends the venv's `Scripts` folder
  to `PATH`, so `key.pem`/`cert.pem` and the `daphne`/`celery` scripts resolve
  even though Windows services start in `System32`.
- **SCRIPT tasks** dispatch `.py` through the interpreter, `.ps1` through
  PowerShell and `.cmd`/`.bat` through `cmd /c` — no shebang/executable bit.
- **MySQL**: `mysqlclient` is skipped on Windows and PyMySQL is registered as
  `MySQLdb` automatically. SQLite remains the default.

## Architecture overview

```
┌────────────────────────────────────────────────────────────┐
│                 Browser (HTML + htmx + SSE)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (pages/fragments) + WebSocket /app/ws/events/
┌──────────────────────▼──────────────────────────────────────┐
│  Django ASGI (Daphne) — webui/ + server/                     │
│  ┌─────────────────┐  ┌───────────────┐  ┌────────────────┐ │
│  │ webui views      │  │ Django        │  │ Events WS +    │ │
│  │ (templates +     │◄─┤ ORM / runtime │◄─┤ Redis pub/sub  │ │
│  │  components)     │  │               │  │ (observables)  │ │
│  └─────────────────┘  └───────────────┘  └────────────────┘ │
└─────────┼────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────┐
│  Runtime / server / registry                                  │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐  │
│  │ Agents    │ │ Sessions  │ │ Tasks      │ │ Loader (YAML)│  │
│  │ (runtime) │ │ (runtime) │ │ (Celery)   │ │ manifest     │  │
│  └────┬─────┘ └────┬─────┘ └──────┬─────┘ └──────┬───────┘  │
└───────┼────────────┼──────────────┼───────────────┼──────────┘
        │            │              │               │
┌───────▼────────────▼──────────────▼───────────────▼──────────┐
│  Django ORM / SQLite or MySQL                                 │
│  ~30 models: Agent, Session, Task, Message, Skill, etc       │
└──────────────────────────────────────────────────────────────┘
```

## Documentation

AgentOne ships with comprehensive documentation organized by audience. Below is the full map — see the [Documentation Map](#documentation-map) for suggested reading order.

| Document | Description |
|---|---|
| `AGENTS.md` | Developer quick reference: directory ownership, key commands, constraints |
| `docs/architecture.md` | System architecture, data flow, component interactions (API/UI/Runtime/Celery) |
| `docs/user-guide.md` | End-user guide: chat, agents, skills, projects, settings, troubleshooting |
| `docs/development.md` | Developer's guide: setup, adding models/tools/agents/UI, testing, REST API |
| `docs/core-mechanisms.md` | Deep-dive: task dispatch pipeline, auto-await, renderer internals (legacy pyHtmlGui section) |
| `docs/ui-rewrite.md` | UI rewrite plan/status: htmx + Django templates + SSE, route map, deferred items |
| `docs/ui-implementation-guide.md` | Normative htmx/SSE/observables rules + agent review checklist for `webui/` changes |
| `docs/deployment.md` | Production deployment: prerequisites, services, nginx, TLS |
| `docs/folders.md` | Canonical filesystem layout: scopes, `var/` subtrees, install repos, backup |
| `docs/manifest-format.md` | YAML manifest format reference (agents, scripts, cron, streams, sets) |
| `docs/models.md` | Model reference (~30 models including DataCollection, full field tables) |
| `docs/skills.yaml.md` | Skill directory structure and manifest format |
| `docs/tool.md` | Tool system quick reference |
| `docs/providers/README.md` | Provider & model research directory (99 providers, 1998 model cards) |


### Documentation map

New to AgentOne?

1. **`README.md`** (this file) — project overview and quick start
2. **`docs/user-guide.md`** — learn the UI from an end-user perspective
3. **`docs/architecture.md`** — understand the system components and data flow
4. **`docs/development.md`** — set up your development environment and add your first model/tool/agent

Building on the platform?

5. **`docs/core-mechanisms.md`** — understand task dispatch and auto-await
6. **`docs/manifest-format.md`** — master YAML manifests for agents, scripts, cron, and data flows
7. **`docs/models.md`** — model reference for all ~30 Django models
8. **`docs/deployment.md`** — deploy to production with Supervisor + Nginx

Quick references:

- `AGENTS.md` — command cheat sheet and gotchas
- `docs/tool.md` — tool system quick reference
- `docs/skills.yaml.md` — skill manifest format
- `docs/providers/README.md` — provider research database

## Project layout

```
config/         Django settings, ASGI/WSGI, Celery app, URL routes
api/            REST API (DRF viewsets, serializers, tests)
server/         Core Django app: models (~30), admin, Celery tasks, tests
registry/       YAML manifest loader pipeline, install repo management
runtime/        Agent/session wrappers, task dispatch state machines, rate limiter
launcher/       Launcher service for remote agent management
webui/          Server-rendered UI: Django templates + htmx + SSE (mounted at /app/)
.agentone/      Active tool/agent configuration: YAML manifests, scripts, skills
docs/           All documentation
```

## Requirements

- Python 3.10+
- Redis 6+ (cache, channels, Celery broker)
- MySQL 8+ optional (SQLite works for development)

See `requirements.txt` for Python package dependencies.
