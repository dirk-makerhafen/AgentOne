ui/
├── app.py                          # UiApp(Observable) — data model
├── app_view.py                     # UiAppView — root view, mounts sidebar + workspace
├── consumer.py                     # WebSocket consumer — unchanged
├── chat/                           # Individual chat item renderers
│   │                               # All used by ChatWorkspaceView's MessageListView
│   ├── message.py                  # ConversationMessageView, MessagePartView
│   │                               #   Default: shows content only
│   │                               #   Expanded: + tool calls inline, query link, response link
│   ├── query.py                    # QueryView, QueryMessageView, QueryMessagePartView
│   │                               #   Hidden by default, linked from message expand
│   ├── response.py                 # ResponseView
│   │                               #   Hidden by default, linked from message expand  
│   ├── task_call.py                # TaskCallView, TaskCallPayloadView,
│   │                               #   TaskRunView, TaskRunPayloadView
│   │                               #   Used both in chat expand and task_workspace
│   ├── log_fs.py                   # FilesystemLogView
│   ├── log_debug.py                # DebugLogView
## │   ├── log_interagent.py           # InterAgentLogView  deprecated, not needed
## │   └── instance_fork.py            # InstanceForkView   deprecated, not needed
│
│
├── panels/                         # Right-side panel tabs (shown in InstanceWorkspaceView)
│   ├── filesystem.py               # FilesystemPanelView, FilesystemItemView, FilesystemHeaderView
│   │                               #   (consolidates filesystem/ folder → 1 file)
│   ├── memory.py                   # MemoryPanelView
│   ├── tasks.py                    # TasksPanelView — task list for this instance
│   ├── tools.py                    # ToolsPanelView
│   ├── subagents.py                # SubagentsPanelView
│   ├── settings.py                 # SettingsPanelView — instance-level settings
## │   ├── permissions.py              # PermissionsPanelView — NEW (tab already exists in UI) deprecated, not needed
## │   ├── events.py                   # EventsPanelView — NEW (tab already exists in UI) deprecated, not needed
│   └── monitor.py                  # MonitorPanelView — NEW: global task monitor
│
│
├── sidebar/
│   ├── sidebar.py                  # SidebarView — container, view mode toggle (agents/dir/hierarchy)
│   ├── agent_tree.py               # SidebarAgentTreeView, SidebarAgentNodeView,
│   │                               #   SidebarVersionNodeView, SidebarVariantNodeView
│   │                               #   (consolidates agentlist+agentnode+versionlist+
│   │                               #    versionnode+variantlist+variantnode → 1 file)
│   └── instance_tree.py            # SidebarInstanceTreeView, SidebarInstanceNodeView
│                                   #   (consolidates instancelist+instancenode → 1 file)

├── workspace/                      # Center: tab bar + all tab content
│   ├── workspace.py                # WorkspaceView — tab bar, open/close/select tabs
│   │
│   ├── instance/                   # Per-agent-instance tabs
│   │   ├── instance_workspace.py   # InstanceWorkspaceView — layout: header + main + right panel
│   │   ├── instance_header.py      # InstanceHeaderView — agent name, model, tokens, status bar
│   │   ├── chat_workspace.py       # ChatWorkspaceView — chat-mode layout (for ChatAgent subclasses)
│   │   │                           #   Detects ChatAgent via: issubclass(agent_cls, ChatAgent)
│   │   │                           #   Contains: MessageListView, InputView
│   │   └── task_workspace.py       # TaskWorkspaceView — task-mode layout (non-ChatAgent)
│   │                               #   Contains: TaskTreeView as primary surface
│   │
│   ├── agent/                      # Per-agent-definition tabs
│   │   ├── agent_workspace.py      # AgentWorkspaceView — layout for agent definition tab
│   │   ├── overview.py             # AgentOverviewView — versions, instances summary
│   │   ├── tasks.py                # AgentTasksView — task definitions + instances
│   │   │                           #   (consolidates agent_task_definitions_view +
│   │   │                           #    agent_task_instances_view → 1 file)
│   │   ├── variants.py             # AgentVariantsView — profile variants
│   │   └── settings.py             # AgentSettingsView — agent-level settings
│   │
│   └── system/                     # Global system tabs (not instance-specific)
│       ├── providers.py            # ProvidersView — API providers + keys + rate limit status
│       ├── systems.py              # SystemsView
## │       ├── prompts.py              # PromptsView   deprecated, not needed
## │       └── tools_registry.py      # ToolsRegistryView   deprecated, not needed
│
│
└── shared/                         # Reusable primitives used across multiple zones
    ├── multi_queryset.py           # MultiQuerySetView — merged sorted queryset renderer
    │                               #   (moved out of chat.py where it doesn't belong)
    ├── detail_settings.py          # DetailSettingsPopover — the gear/sliders icon + popover
    │                               #   controls which log types are visible per instance
    │                               #   options: show_queries, show_fs_logs, show_debug_logs,
    │                               #            show_task_calls, detail_level (simple/developer)
    └── status_badge.py             # StatusBadgeView — reusable status pill
                                    #   used by TaskCallView, InstanceHeaderView, sidebar nodes