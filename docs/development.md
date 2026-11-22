# Development guide

## Project setup

```bash
# Clone and enter project
git clone <repo> agentone && cd agentone

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration wizard — asks about DB type (SQLite/MySQL),
# Redis URL, generates SECRET_KEY and TLS certificate,
# runs migrations, and optionally creates a superuser
python3 manage.py server setup

# Run (starts Daphne + Celery worker + Celery beat)
python3 manage.py server run

# Update (git pull + pip install + migrate + reload)
python3 manage.py server update
```

Open http://localhost:8000.

### Manual configuration

If you prefer to skip the wizard, copy the example file and edit:

```bash
cp config/settings_local.example.py config/settings_local.py
```

Key settings you can override in `settings_local.py`:

| Setting | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | auto-generated | Django CSRF/session signing |
| `AGENT_SERVER_SECRET_KEY` | auto-generated | Client registration shared secret |
| `DEBUG` | `False` | Enable dev debug mode |
| `ALLOWED_HOSTS` | `["*"]` | Production: restrict to your domain |
| `DATABASES` | SQLite | Switch to MySQL for production |
| `REDIS_URL` | `redis://localhost:6379/1` | Cache, channels, Celery broker |
| `LISTEN_ADDRESS` | `0.0.0.0` | Daphne bind address |
| `LISTEN_PORT` | `7999` | Daphne TLS port |

No secrets are stored in version control — `settings_local.py` is gitignored.

### Setup wizard reference

`python3 manage.py server setup` walks through configuration interactively:

| Prompt | Default | Notes |
|---|---|---|
| **Database backend** | SQLite (1) | Choose 1 for SQLite, 2 for MySQL |
| SQLite database path | `<project>/db.sqlite3` | Only asked for SQLite |
| MySQL host | `localhost` | Only asked for MySQL |
| MySQL port | `3306` | |
| Database name | `AgentOne_v3` | |
| MySQL user | *(blank for socket auth)* | Leave empty to omit USER/PASSWORD |
| MySQL password | *(blank for no password)* | Only asked if user is non-empty |
| **Redis URL** | `redis://localhost:6379/1` | Cache, channels, Celery broker |
| **HTTP listen address** | `0.0.0.0` | Daphne bind address |
| **HTTP listen port** | `7999` | Daphne TLS port |
| **Generate TLS cert** | Yes | Creates `cert.pem` + `key.pem` (self-signed) |
| **Create superuser** | Yes | Only shown if no superuser exists |
| Admin username | `admin` | |
| Admin email | `admin@localhost` | |
| Admin password | *(blank for random)* | Random 16-char token printed if left empty |

On completion the wizard: writes `config/settings_local.py`, runs `migrate`, and creates the superuser (if requested). The server is then ready with `python3 manage.py server run`.

## Code organization

```
config/             Django configuration
  settings.py       DB, Redis, Celery, installed apps, middleware
  urls.py           URL routing: UI, admin, web API (api/v1/), accounts
  asgi.py           ASGI app with Channels WebSocket at /ws
  wsgi.py           WSGI app
  celery.py         Celery app with beat schedule

api/                REST API (Django REST Framework)
  urls.py           Route registration (DRF DefaultRouter)
  pagination.py     Custom pagination (PageNumberPagination)
  permissions.py    Permission classes (DjangoModelAdminOrAnonReadOnly)
  serializers/      Per-domain serializers with runtime resolution
  views/            Per-domain ViewSets + function endpoints
  tests/            pytest test suite (67 tests)

server/             Core Django app
  models/           ~30 model classes organized by domain
  admin/            Django admin registrations
  tasks/            Celery tasks: tick_scheduler (10s), cron_scheduler +
                    sleep_guard_scheduler (60s), recovery_scheduler (disabled),
                    startup_cleanup, heartbeat, dispatcher
  prompts.py        System prompt template builder
  signals.py        Model signal handlers (auto-reload on save)
  migrations/       67 migration files
  tests/            Django tests

registry/           YAML manifest loader
  loader/           Loader pipeline: agent, scripts, skill, chain, python
  sources/          Upstream git repo sync — skills, agents, scripts
  install_repo.py   Git-based runtime folder extraction
  task_decorators.py  Legacy @task/@tool/@command (dead code)

runtime/            Execution runtime
  session/          Session wrapper (copy-on-write property access)
  agents/           Agent wrapper (name resolution via allow/deny)
  tasks/            Task dispatch: BoundTask, call/run state machines + schedulers
  rate_limiter.py   3-tier rate limiter (provider→model→apikey)
  runtime_folder.py Versioned file extraction from git trees
  project/          Project runtime wrapper
  skill/            Skill runtime wrapper
  workspace/        Workspace runtime wrapper
  cron/             Cron runtime wrapper

webui/              Server-rendered UI (Django templates + htmx + SSE)
  core/             Layout, components registry, events bridge, shared utilities
  features/         Feature apps (chats, projects, agents, settings, ...)
  static/           CSS/JS assets (including ws-events + app JS)
  templates/        Django templates (base, feature pages/fragments)
  urls.py           /app routes (mounted via config.urls -> webui.urls)

.agentone/          Active configuration (global scope; see docs/folders.md)
  agents/           Agent definitions (agent.md files with YAML frontmatter)
  scripts/          Tool/task scripts organized by group
  skills/           Skill installation configuration
```

### Observable ORM subscriptions

`runtime.observable_queries` exposes callback-based subscriptions for
explicitly supported live query shapes. A subscription registers its Redis
event keys before reading the initial rows, buffers concurrent changes until
the initial `snapshot` callback is delivered, then sends `upsert` and `remove`
events to the same callback. Call `close()` or use the subscription as a
context manager to unregister it.

```python
from runtime.observable_queries import ObservableProject, ObservableRoot, ObservableSession

subscription = ObservableRoot().get_agents(handle_agent_events)
project_subscription = ObservableProject(project).get_skills(handle_skill_events)
session_subscription = ObservableSession(session).get_messages(handle_message_events)
```

The public API intentionally contains only named query methods. It does not
accept arbitrary models, querysets, relation names, or filters: if a query
shape is not exposed as a named method, it is not currently supported as an
observable subscription. Every event delivered to observers includes the
serialized row and a revision timestamp. The row is refreshed and serialized
once per model change, regardless of the number of subscribers; changes with
no subscribers avoid the refresh and serialization. Sensitive fields such as
API credentials are excluded by the model serializer. Collection order is
unspecified: callbacks describe membership and item changes, not a stable
ordering. These subscriptions are an internal Python callback API; they do
not yet change the UI or `QuerySetView`.

## How to add a new model

1. Create the model file in `server/models/<domain>/<name>.py`:

```python
from server.models.base_model import BaseModel

class MyModel(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("AgentModel", on_delete=models.CASCADE, null=True)

    class Meta:
        verbose_name = "My Model"
```

2. Export from `server/models/__init__.py`:

```python
from .my_model import MyModel
```

3. Register in admin (`server/admin/<name>.py`):

```python
from django.contrib import admin
from server.models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ("name", "owner")
```

4. Create and run migration:

```bash
python3 manage.py makemigrations server
python3 manage.py migrate
```

5. If the model needs a runtime wrapper, add it in `runtime/<domain>/`:

```python
# runtime/my_models/my_model.py
from server.models import MyModel

class MyModelRuntime:
    def __init__(self, model: MyModel):
        self.model = model
```

## How to add a new tool

1. Create a script in `.agentone/scripts/<group>/<name>.py`:

```python
"""Tool description (used as schema description)."""

from typing import Any

__group__ = "my_group"

def my_tool(param1: str, param2: int = 0) -> tuple[bool, dict[str, Any]]:
    """
    Tool description for LLM.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 0)
    """
    try:
        result = do_something(param1, param2)
        return True, {"result": result}
    except Exception as e:
        return False, {"error": str(e)}
```

2. Register in `.agentone/scripts/<group>/scripts.md`:

```yaml
---
name: my_group
tools:
  my_tool: my_tool.py
---
```

3. Add tests in `.agentone/scripts/<group>/test_<name>.py`:

```python
from scripts.<group>.<name> import my_tool

def test_my_tool():
    ok, data = my_tool("test")
    assert ok
    assert "result" in data
```

4. The schema (function signature + docstring) is auto-extracted — no decorators needed.

**Annotation gotcha:** the schema generator maps `Any` and bare `dict` to
`{"type": "string"}` — only `typing.Dict` / `dict[...]` (optionally
`Optional[...]`-wrapped) produce `{"type": "object", ...}`. So for any
parameter that must arrive as a JSON object, annotate it e.g.
`params: Optional[Dict] = None`, never `params: Any = None`. A wrong
annotation does not fail at load time; the LLM just sends a JSON string
and the tool has to parse (or reject) it at runtime.

## How to add a new agent

1. Create agent manifest at `.agentone/agents/<name>/agent.md`:

```yaml
---
name: my_agent
model: gemma4:26b
tools:
  - my_group.*
tasks:
  - core.*
skills:
  - document-scanner
extend: baseagent
settings:
  reasoningEffort: high
  schedulerStrategy: queue
---
Optional system prompt in markdown after the frontmatter.
```

2. If the agent needs custom commands, add a `scripts/` subdirectory:

```python
# .agentone/agents/my_agent/scripts/my_command.py
def my_command() -> tuple[bool, dict]:
    return True, {"message": "hello"}
```

3. Register in `.agentone/agents/my_agent/scripts/scripts.md`:

```yaml
---
name: my_agent_commands
commands:
  my_command: my_command.py
---
```

## How to add a new UI surface (webui)

The UI is server-rendered in `webui/` (Django templates + htmx + SSE). Follow current patterns:

- Feature code lives under `webui/features/<name>/` (views, components, templates).
- Register independently cacheable fragments/components via `webui/core/components.py` (`register_component`) and wire URLs in `webui/urls.py`.
- Use observable keys + SSE triggers per [`docs/htmx-sse.md`](htmx-sse.md) and [`docs/ui-implementation-guide.md`](ui-implementation-guide.md).
- For sidebar sections, follow existing section/sidebar patterns in `webui/core/components.py` and feature templates.

Do not add new `ui/` pyHtmlGui (`PyHtmlView`/`pyview.*`) code; that stack was removed.

## REST API

AgentOne provides a comprehensive REST API at `/api/v1/` backed by Django REST Framework.

### Quick start

```bash
# Obtain a JWT token
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'

# Use the token for authenticated requests
TOKEN="eyJ0eXAiOiJKV1Qi..."
curl http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $TOKEN"

# Health check (no auth required)
curl http://localhost:8000/api/v1/health/
```

### API docs (OpenAPI)

| URL | Description |
|---|---|
| `/api/v1/schema/` | OpenAPI 3.0 JSON schema (use with `drf-spectacular`) |
| `/api/v1/docs/` | Swagger UI interactive explorer |
| `/api/v1/redoc/` | ReDoc documentation viewer |

### Endpoints

| Prefix | Description | Auth |
|---|---|---|
| `auth/token/` | JWT obtain + refresh | None (credentials in body) |
| `health/` | DB + Redis connectivity | None |
| `me/` | Current user profile | Required |
| `agents/` | Full CRUD + `/commands/`, `/tasks/`, `/tools/`, `/skills/`, `/subagents/`, `/versions/` | Required |
| `sessions/` | Full CRUD + `/message/`, `/messages/`, `/call/{name}/`, `/reset/` | Required |
| `queries/` | Read-only list/detail + `/cancel/` | Required |
| `collections/` | Full CRUD + `/items/`, `/reprocess/` | Required |
| `cron/` | Full CRUD + `/run/` | Required |
| `providers/` | Read-only list/detail | Required |
| `models/` | Read-only list/detail | Required |
| `skills/` | Read-only list/detail + `/versions/` | Required |
| `projects/` | Full CRUD | Required |
| `systems/` | Full CRUD | Required |
| `workspaces/` | Full CRUD | Required |
| `task-calls/` | Read-only list/detail with nested runs | Required |
| `task-runs/` | Read-only list/detail | Required |

### Common query parameters

Every viewset supports:

```bash
# Filter by exact field match
curl "$BASE/agents/?name=baseagent"
curl "$BASE/collections/?collection_type=stream"

# Full-text search across searchable fields
curl "$BASE/agents/?search=base"
curl "$BASE/sessions/?search=my-chat"

# Ordering (ascending by default, prefix - for descending)
curl "$BASE/agents/?ordering=-created_at"

# Pagination (default page_size=10)
curl "$BASE/agents/?page=2&page_size=50"
```

### Key patterns

**Session message:**

```bash
# String content
curl -X POST "$BASE/sessions/1/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "hello"}'

# Structured parts
curl -X POST "$BASE/sessions/1/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "", "parts": [{"type": "text", "text": "hello"}]}'
```

**Task call on a session:**

```bash
curl -X POST "$BASE/sessions/1/call/ping/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"args": ["hello"], "kwargs": {}}'
```

**Session settings (PATCH updates via runtime copy-on-write):**

```bash
curl -X PATCH "$BASE/sessions/1/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "renamed-session", "aimodel": 42}'
```

### Architecture

The API sits between the HTTP client and the Django application:

```
HTTP client → DRF ViewSets → runtime wrappers → Django models
```

Rules for what gets exposed:
- **Agents**: resolves inherited capabilities (`allowedCommands`, `allowedTools`, etc.) from the version chain, not raw M2M fields
- **Sessions**: exposes `get_messages()`, settings via copy-on-write (`_safe_runtime_settings()`)
- **Queries**: read-only — created internally by the session message flow
- **Providers/Models**: read-only — managed through Django admin
- **Task calls/runs**: read-only — expose `result_json` and `arguments_json` for full execution trace

### Adding a new endpoint

1. Create the view in `api/views/<name>.py`:
```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

class MyViewSet(viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['name', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = '__all__'
```

2. Create the serializer in `api/serializers/<name>.py`:
```python
from rest_framework import serializers
from server.models import MyModel

class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
```

3. Register the route in `api/urls.py`:
```python
router.register(r'my-items', MyViewSet, basename='my-item')
```

4. Add tests in `api/tests/test_<name>.py` with fixtures from `conftest.py`.

### Running API tests

```bash
# All API tests
python3 -m pytest api/tests/ -v

# Single file
python3 -m pytest api/tests/test_agents.py -v

# With schema validation
python3 -m pytest api/tests/test_schema.py -v
```
## Running tests

```bash
# Tool tests (75 total)
python3 -m pytest .agentone/scripts/ -v

# Django tests (may require MySQL)
python3 -m pytest server/tests/ -v

# Specific tool test
python3 -m pytest .agentone/scripts/filesystem/read/test_read.py -v
```

## Guardrails

Shell and Python commands are automatically scanned before execution by the guardrail system in `runtime/guardrails.py`.

- **Shell commands** → [sh-guard](https://github.com/aryanbhosale/sh-guard) (AST-based risk classifier) + pureshellcheck linting
- **Python code** → [bandit](https://github.com/PyCQA/bandit) (PyCQA security linter) + supplementary AST checks for patterns bandit misses (socket, ctypes, open modes, os.remove, compile)
- **Pre-schedule** (threshold 80) runs before a call is dispatched; risky commands enter `HALTED_APPROVAL` for human decision
- **Execution-time** (threshold 90) runs again just before `subprocess.run()` as a second line of defense
- Guardrails are always advisory — they never silently deny; the user always gets an approve/deny card
- Tests live in `server/tests/test_guardrails.py` (36 unit tests) and `api/tests/test_tasks.py` (24 integration tests)

## Linting

```bash
python3 -m pylint config/ server/ registry/ tools/
```

`.pylintrc` sets `max-line-length=200` and disables `C0114/C0115/C0116`.

## Coding conventions

- **Use `python3`**, not `python`
- Models extend `server.models.base_model.BaseModel` (adds dirty tracking, immutable save)
- Versioned models raise `ValidationError` on save — create new versions instead
- UI views extend `ui.lib.model_view.ModelView` (adds `.subject`, `.parent`, auto-update)
- Templates use Jinja2 with only `{"pyview": self}` in context
- Tool functions follow the `(bool, dict)` return convention
- CSS uses custom properties (`var(--color)`) for theming; add new ones to `:root` blocks
- All user-facing text should include `data-i18n="key"` for future localization

## Project configuration

- `config/settings.py` defaults to SQLite with safe dev values
- `config/settings_local.py` is gitignored — create it via `python3 manage.py server setup` or copy `settings_local.example.py`
- `cert.pem` and `key.pem` are gitignored — auto-generated by the setup wizard
- Redis must be running at `localhost:6379` for full stack (channels, cache, celery)
- Celery beat must be running — it drives the 5s tick scheduler
- `old/` directory is dead code — do not modify

## Upstream sources

AgentOne can pull agents, scripts, and skills from remote git repositories. Configure upstream repos in per-directory YAML files:

| File | Source for |
|---|---|
| `.agentone/skills/skills.yaml` | Skill upstream repos |
| `.agentone/agents/sources.yaml` | Agent upstream repos |
| `.agentone/scripts/sources.yaml` | Script/tool upstream repos |

**Format:**

```yaml
sources:
  - repo: https://github.com/agentone/official-skills.git
    ref: main
  - repo: https://github.com/community/extra-tools.git
    ref: v2.1
    include: [filesystem/*, git/*]   # optional glob filter
```

**Merge semantics:**

1. On every `reload_all`, upstream repos are cloned/fetched into `~/.agentone/var/cache/upstream/`
2. A staging directory is built — upstream content first, then local `.agentone/` files overlay on top
3. **Local files always win** on path conflicts
4. The merged staging directory becomes the install repo's source root — version tracking (git tree SHAs) works identically for upstream and local files

**Server update:**

```
python3 manage.py server update
```

This runs `git fetch`, `git pull --ff-only`, `pip install -r requirements.txt`, `migrate`, `collectstatic` (unless `DEBUG` is on), `reload_all`, and schedules a service restart — safe to run while the server is down. Add `--check` to only print version/remote status, `--force` to rerun the pipeline when already current, `--allow-dirty` to update over local edits, or `--no-restart` to skip the restart. The same code is used by the staff-only **Settings → System → Update AgentOne** button in the UI; set `AGENTONE_UPDATE_CHECK_ENABLED = False` to disable its remote lookup.

---

**See also:** [Architecture](architecture.md) · [Core mechanisms](core-mechanisms.md) · [Manifest format](manifest-format.md) · [Deployment](deployment.md)
