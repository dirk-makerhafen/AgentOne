# UI directory structure

```
ui/
├── app.py                  # UiApp(Observable) — data model root, holds all runtime managers
├── app_view.py             # UiAppView(PyHtmlView) — root view, mounts full UI layout
├── consumer.py             # PyHtmlGuiConsumer(WebsocketConsumer) — Django Channels WS bridge
│
├── lib/                    # Reusable base classes
│   ├── model_view.py       # ModelView(PyHtmlView) — base for all AgentOne views (subject/parent/auto-update)
│   ├── queryset_view.py    # QuerySetView(ModelView) — renders Django QuerySets as lazy child lists
│   ├── multi_queryset_view.py  # MultiQuerySetView — merges multiple querysets into one sorted list
│   ├── status_badge.py     # StatusBadgeView — status pill (success/error/waiting/active/halted/neutral)
│   └── pyHtmlGui/          # Vendored pyHtmlGui framework (git submodule)
│
├── sidebar/                # Left sidebar + rail
│   ├── sidebar.py          # SidebarView — container, panel switching, project filter
│   ├── rail.py             # RailView — vertical icon nav bar (desktop)
│   ├── project_selector.py # ProjectSelector + ProjectOption — dropdown project filter
│   └── panels/
│       ├── agents.py       # Agent profile list
│       ├── chats.py        # Session/conversation list with search + context menu
│       ├── cron.py         # Scheduled jobs list
│       ├── insights.py     # Opens dashboard on activation
│       ├── logs.py         # Log viewer controls (file, tail, auto-refresh)
│   ├── dataflows.py    # Data collections (streams/sets) list
│       ├── projects.py     # Project list
│       ├── settings.py     # Settings menu (opens SettingsView in main)
│       ├── skills.py       # Skill list with search
│       └── workspaces.py   # Workspace list
│
├── main/                   # Main content area (tabs)
│   ├── main_view.py        # MainView — tab container, open/close/select
│   ├── agent/              # Agent profile detail
│   ├── chat/               # Chat workspace (messages + composer + cards + banners)
│   │   ├── chat.py         # Chat — full chat workspace
│   │   ├── messages/       # Message rendering (user, assistant, tool cards, query)
│   │   ├── composer/       # Input area (textarea, footer, dropdowns)
│   │   ├── cards/          # Flyout cards (approval, clarify, queue)
│   │   ├── banner/         # Status banners (health, reconnect, update)
│   │   └── panel/          # Side panels (terminal, mobile config)
│   ├── cron/               # Cron job detail + creation
│   ├── insights/           # Dashboard view (system health, metrics)
│   ├── logs/               # File log display
│   ├── memory/             # Agent memory browser
│   ├── collections/        # Data flow detail + creation
│   ├── project/            # Project detail/editor
│   ├── rightpanel/         # Right-side tabs (session, tasks, workspace, subagents)
│   ├── settings/           # Full settings tabs (conversation, appearance, preferences, providers, system)
│   ├── skills/             # Skill detail/editor
│   ├── system/             # Providers view, systems view
│   └── workspace/          # Workspace detail + creation
│
├── overlay/                # Overlay views
│   ├── appdialog.py        # Modal dialog (confirm, input)
│   ├── mobile.py           # Mobile sidebar backdrop
│   └── onboarding.py       # First-run wizard
│
├── static/
│   ├── css/
│   │   └── main.css        # 3800+ lines — single stylesheet, 7 color skins, light/dark
│   ├── css3party/          # Bootstrap, font-awesome, jquery-ui, d3-flamegraph, diff2html
│   ├── js/                 # marked.umd.js, resizable.js, splitpanel.js, tabs.js
│   ├── js3party/           # jQuery, Bootstrap, D3, Split.js, diff, handlebars
│   └── fonts/              # glyphicons, fontawesome
│
├── templates/
│   ├── pyhtmlgui_page.html # Main page template (overrides base with static assets)
│   ├── pyHtmlGuiBase.html  # Base HTML: WebSocket client, pyhtmlgui JS API
│   ├── registration/       # Django auth login template
│   └── test.html           # Layout test page (Split.js)
│
└── README.md               # This file
```

## Architecture notes

- **Single shared instance**: `PyHtmlGuiConsumer` creates one `UiApp` + one `UiAppView` shared across all WebSocket connections.
- **Reactive updates**: Views observe `Observable` subjects. When the model changes, all attached views call `update()` which re-renders via Jinja2 and patches the DOM over WebSocket.
- **Lazy panels**: `QuerySetView` only creates child views when the panel is visible. Switching panels destroys the old children.
- **No i18n yet**: All user-facing text has `data-i18n="key"` attributes stubbed, but no locale files exist.
- **Panel pattern**: Each sidebar panel follows `SidebarPanelXxx` (container) + `SidebarPanelXxxItem` (row) pattern, with `set_project_filter(pid)` for project-aware filtering.

## Adding a new panel

See [docs/development.md](../docs/development.md) for the full guide.
