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
# Redis URL, generates SECRET_KEY and TLS certificate
python3 manage.py server setup

# Apply database migrations
python3 manage.py migrate

# Run (starts Daphne + Celery worker + Celery beat)
python3 manage.py server run
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
| `LISTEN_PORT` | `8001` | Daphne TLS port |

No secrets are stored in version control — `settings_local.py` is gitignored.

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
  tasks/            Celery tasks: tick_scheduler, heartbeat, dispatcher
  prompts.py        System prompt template builder
  signals.py        Model signal handlers (auto-reload on save)
  migrations/       67 migration files
  tests/            Django tests

registry/           YAML manifest loader
  loader/           Loader pipeline: agent, scripts, skill, chain, python
  install_repo.py   Git-based runtime folder extraction
  task_decorators.py  Legacy @task/@tool/@command (dead code)

runtime/            Execution runtime
  session/          Session wrapper (copy-on-write property access)
  agents/           Agent wrapper (name resolution via allow/deny)
  tasks/            Task dispatch: BoundTask, call/run state machines + schedulers
  rate_limiter.py   3-tier rate limiter (provider→model→apikey)
  runtime_folder.py Versioned file extraction from git trees
  project/          Project runtime wrapper
  pipe/             Pipe runtime wrapper
  skill/            Skill runtime wrapper
  workspace/        Workspace runtime wrapper
  cron/             Cron runtime wrapper

ui/                 Web UI (pyHtmlGui)
  app.py            UiApp (Observable data model root)
  app_view.py       UiAppView (root view, mounts full layout)
  consumer.py       WebSocket consumer (Django Channels)
  lib/              Reusable base classes (ModelView, QuerySetView, etc.)
  lib/pyHtmlGui/    Custom UI framework vendor
  sidebar/          Sidebar panels + rail + project selector
  main/             Main panel: chat, settings, agents, projects, etc.
  overlay/          Overlays: onboarding, dialog, mobile
  static/css/       Main stylesheet (3800+ lines), third-party CSS
  static/js/        Custom JS (resizable, split panel, tabs)
  static/js3party/  Vendored JS (jQuery, Bootstrap, D3, Split.js, etc.)
  templates/        Jinja2 base templates

.agentone/          Active configuration
  agents/           Agent definitions (agent.md files with YAML frontmatter)
  scripts/          Tool/task scripts organized by group
  skills/           Skill installation configuration
  projects.yaml     Project path references
```

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

## How to add a new UI panel

### Sidebar panel

1. Create the panel file at `ui/sidebar/panels/<name>.py`:

```python
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

class SidebarPanelMyItems(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = """
        <div class="panel-head">
            <span>My Items</span>
            <button onclick="pyview.addItem()">+</button>
        </div>
        {{ pyview.list_view.render() }}
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.list_view = QuerySetView(
            subject=self.subject,
            parent=self,
            queryset=MyModel.objects.all(),
            item_view_class=SidebarPanelMyItem,
        )

    def set_project_filter(self, project_id: int | None) -> None:
        qs = MyModel.objects.all()
        if project_id:
            qs = qs.filter(parent_project_id=project_id)
        self.list_view.queryset = qs
        self.list_view.recreate()

class SidebarPanelMyItem(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "session-item"
    TEMPLATE_STR = """<div>{{ pyview.subject.name }}</div>"""
```

2. Register in `ui/sidebar/sidebar.py`:

```python
from ui.sidebar.panels.my_items import SidebarPanelMyItems

# In SidebarView.__init__:
self.panels["my_items"] = SidebarPanelMyItems(
    subject=self.subject, parent=self
)
```

3. Add a rail button in `ui/sidebar/rail.py`:

```python
<button class="nav-tab" data-panel="my_items" onclick="pyview.parent.sidebar.switchPanel('my_items')">
    ...
</button>
```

### Main panel tab

1. Create the view at `ui/main/<domain>/<name>.py`:

```python
from ui.lib.model_view import ModelView

class MyDetailView(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "my-detail"
    TEMPLATE_STR = """
        <h2>{{ pyview.subject.name }}</h2>
        <p>{{ pyview.subject.description }}</p>
    """
```

2. Open from sidebar with:

```python
self.root_view.main.create_and_open_tab(MyDetailView, subject=my_model_instance)
```

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

Now continuing with test commands for Django server tests:

## Running tests

```bash
# Tool tests (73 total)
python3 -m pytest .agentone/scripts/ -v

# Django tests (may require MySQL)
python3 -m pytest server/tests/ -v

# Specific tool test
python3 -m pytest .agentone/scripts/filesystem/read/test_read.py -v
```

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
