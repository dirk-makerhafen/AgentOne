# AgentOne

AgentOne is a Django-based autonomous agent framework with real-time Web UI, scheduled task execution, and a plugin-based tool system. It manages multiple AI agents with versioned configurations, tools, skills, and session state — all accessible through a browser-based chat interface.

## Features

- **Multi-agent runtime** — Run multiple agents with independent configurations, models, and tool sets, each with version-pinned agent definitions
- **Real-time WebSocket UI** — Custom pyHtmlGui framework delivers live DOM updates over WebSocket; no page reloads, no REST boilerplate
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

```bash
# Prerequisites: Python 3.10+, Redis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Interactive setup — database, Redis, TLS certificate
python3 manage.py server setup

# Run (starts Daphne + Celery worker + Celery beat)
python3 manage.py server run
```

Open http://localhost:8000 to see the UI.

### Updating

```bash
python3 manage.py server update
```

Runs `git pull`, `pip install -r requirements.txt`, `migrate`, and `reload_all` in sequence.

## Architecture overview

```
┌────────────────────────────────────────────────────────────┐
│                     Browser (WebSocket)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ /ws
┌──────────────────────▼──────────────────────────────────────┐
│  Django ASGI / Channels / PyHtmlGuiConsumer                 │
│  ┌─────────────┐  ┌──────────┐  ┌─────────────────────────┐│
│  │ UiApp        │  │ UiAppView │  │ pyHtmlGui (DOM sync)   ││
│  │ (Observable) │◄─┤ (root     │◄─┤ Jinja2→HTML→WebSocket  ││
│  │ data model   │  │  view)   │  │                         ││
│  └──────┬───────┘  └──────────┘  └─────────────────────────┘│
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
| `docs/core-mechanisms.md` | Deep-dive: task dispatch pipeline, auto-await, pyHtmlGui renderer internals |
| `docs/deployment.md` | Production deployment: prerequisites, services, nginx, TLS |
| `docs/manifest-format.md` | YAML manifest format reference (agents, scripts, cron, streams, sets) |
| `docs/models.md` | Model reference (~30 models including DataCollection, full field tables) |
| `docs/skills.yaml.md` | Skill directory structure and manifest format |
| `docs/tool.md` | Tool system quick reference |
| `docs/providers/README.md` | Provider & model research directory (99 providers, 1998 model cards) |
| `ui/README.md` | UI directory structure and component reference |

### Documentation map

New to AgentOne?

1. **`README.md`** (this file) — project overview and quick start
2. **`docs/user-guide.md`** — learn the UI from an end-user perspective
3. **`docs/architecture.md`** — understand the system components and data flow
4. **`docs/development.md`** — set up your development environment and add your first model/tool/agent

Building on the platform?

5. **`docs/core-mechanisms.md`** — understand task dispatch, auto-await, and the pyHtmlGui renderer
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
ui/             Web UI: pyHtmlGui views, sidebar, chat, settings, overlays
.agentone/      Active tool/agent configuration: YAML manifests, scripts, skills
docs/           All documentation
```

## Requirements

- Python 3.10+
- Redis 6+ (cache, channels, Celery broker)
- MySQL 8+ optional (SQLite works for development)

See `requirements.txt` for Python package dependencies.
