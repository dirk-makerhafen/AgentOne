# Development guide

## Project setup

```bash
# Clone and enter project
git clone <repo> agentone && cd agentone

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database (MySQL)
mysql -u root -e "CREATE DATABASE AgentOne_v3 CHARACTER SET utf8mb4;"
python3 manage.py migrate

# Redis (must be running at localhost:6379)
redis-server

# Run
python3 manage.py runserver           # dev server
python3 -m celery -A config worker -l INFO   # worker
python3 -m celery -A config beat -l INFO     # beat scheduler
```

Open http://localhost:8000.

## Code organization

```
config/             Django configuration
  settings.py       DB, Redis, Celery, installed apps, middleware
  urls.py           URL routing: UI, admin, web API, accounts
  asgi.py           ASGI app with Channels WebSocket at /ws
  wsgi.py           WSGI app
  celery.py         Celery app with beat schedule

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

- `config/settings.py` uses MySQL by default; uncomment lines 16-23 and comment 24-34 for SQLite
- `config/settings_local.py` is gitignored for local overrides
- Redis must be running at `localhost:6379` for full stack (channels, cache, celery)
- Celery beat must be running — it drives the 5s tick scheduler
- `old/` directory is dead code — do not modify
