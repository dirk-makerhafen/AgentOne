# AgentOne

AgentOne is a Django-based autonomous agent framework with real-time Web UI, scheduled task execution, and a plugin-based tool system. It manages multiple AI agents with versioned configurations, tools, skills, and session state — all accessible through a browser-based chat interface.

## Features

- **Multi-agent runtime** — Run multiple agents with independent configurations, models, and tool sets, each with version-pinned agent definitions
- **Real-time WebSocket UI** — Custom pyHtmlGui framework delivers live DOM updates over WebSocket; no page reloads, no REST boilerplate
- **Versioned everything** — Agents, tools, sessions, and settings are immutable once created; changes produce new versions with full history
- **Plugin tool system** — Tools are plain Python functions in YAML-defined groups with auto-extracted JSON schemas — no decorators
- **Celery task pipeline** — Asynchronous task dispatch with scheduling (5s tick, 2min heartbeat), state machine execution, and dependency resolution via M2M references
- **Subagent delegation** — Agents can spawn subagents with `delegate_task`/`spawn_subagent`, with automatic await and result delivery
- **Data flows (streams / ordered sets)** — Agents produce data into append-only streams or mutable ordered sets, which cascade to derived flows via propagation. Replaces legacy named pipes.
- **Project organization** — Agents, skills, and sessions can be grouped into projects with filtering across the sidebar
- **Rate limiting** — Three-tier rate limiting (provider → model → API key) with per-minute/per-day token and request limits
- **Multi-skin UI** — 7 built-in color skins (default gold, ares red, mono gray, slate, poseidon ocean, sisyphus purple, charizard orange) with light/dark mode
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

| Document | Description |
|---|---|---|
| `AGENTS.md` | Quick reference: stack, directory ownership, key commands, constraints |
| `docs/architecture.md` | Deep-dive into architecture, data flow, component interactions |
| `docs/development.md` | Developer's guide: setup, adding models/tools/agents/UI, testing, REST API, upstream sources |
| `docs/deployment.md` | Production deployment: prerequisites, services, nginx, TLS |
| `docs/core-mechanisms.md` | Task dispatch pipeline, auto-await, pyHtmlGui renderer internals |
| `docs/manifest-format.md` | YAML manifest format reference (agents, scripts, cron, streams, sets, upstream sources) |
| `docs/models.md` | Model reference (~30 models including DataCollection) |
| `docs/skills.yaml.md` | Skill manifest format and upstream installation |
| `ui/README.md` | UI directory structure and component reference |

## Project layout

```
config/         Django settings, ASGI/WSGI, Celery app, URL routes
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
