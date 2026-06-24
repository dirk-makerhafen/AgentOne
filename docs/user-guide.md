# User guide

## Getting started

Open AgentOne in your browser at the URL where it's hosted (default: `http://localhost:8000`). If authentication is enabled, log in with your credentials. On first visit, the onboarding overlay may guide you through initial setup.

### Interface layout

```
┌──────────────────────────────────────────────────────────────┐
│  Title Bar                                                    │
├────┬──────────┬───────────────────────────────┬───────────────┤
│    │ Project  │                               │               │
│ R  │ Selector │     Main Panel (tabs)         │  Right Panel  │
│ a  ├──────────┤                               │  (session,    │
│ i  │ Sidebar  │  Chat / Settings / Agent /    │   tasks,      │
│ l  │ Panels   │  Project / Workspace / ...    │   workspace,  │
│    │          │                               │   subagents)  │
│    │ Chats    │                               │               │
│    │ Agents   │                               │               │
│    │ Skills   │                               │               │
│    │ ...      │                               │               │
├────┴──────────┴───────────────────────────────┴───────────────┤
│  Status Bar (optional)                                         │
└──────────────────────────────────────────────────────────────┘
```

The interface has four main zones:

| Zone | Purpose |
|---|---|
| **Rail** (left icon strip) | Switch between sidebar panels: Chats, Cron, Data Flows, Agents, Projects, Workspaces, Skills, Memory, Kanban, Todos, Insights, Logs, Settings |
| **Sidebar** | Lists items for the selected panel: sessions, agents, skills, cron jobs, etc. |
| **Main panel** | Primary workspace — opens tabs for chatting, editing settings, viewing agent details, etc. |
| **Right panel** | Contextual details about the active selection: session info, task calls, workspace files, subagents |

---

## Chat

The chat panel is the primary interface for interacting with AI agents.

### Starting a conversation

1. Click the **Chats** icon in the rail (or ensure it's selected in the sidebar)
2. Click **+ New conversation** at the top of the sidebar
3. A new chat tab opens in the main panel

### Sending messages

Type your message in the composer box at the bottom of the chat panel and press **Enter** or click the send button. The agent processes your message and responds. Each response may include:
- **Text response** — the agent's reply
- **Reasoning** — the agent's internal thought process (collapsible, hidden by default)
- **Tool calls** — expandable cards showing tool execution details

### Tool approval

When a tool or command requires human approval, an **Approval Card** slides up over the composer:

- **Approve** — allow the tool/command to execute
- **Deny** — reject the tool/command
- **Review details** — expand the card to see the function, arguments, and description

Approval can be triggered in two ways:

- **Static** — the tool's `scripts.md` manifest has `requires_approval: true`
- **Dynamic (guardrails)** — before a shell or Python command runs, it is scanned by safety guardrails. Shell commands are classified by **sh-guard** (AST-based risk scoring); Python code is analyzed by **bandit** (PyCQA security linter). If the guardrail deems a command risky (score ≥ 80), the call enters `HALTED_APPROVAL` state and an approval card is shown even if the tool itself does not require approval. Execution-time guardrails use a higher threshold (score ≥ 90) for a second line of defense.

### Queue

If the agent is busy processing, a **Queue Card** shows the pending messages. You can cancel queued messages or wait for them to process.

### Clarification

When the AI needs clarification, a **Clarify Card** presents choices. Select an option to continue.

### Session management

In the chat sidebar, each conversation has a context menu (three dots icon) with actions:

| Action | Description |
|---|---|
| **Pin** | Pin the conversation to the top of the list |
| **Move to project** | Reassign the session to a different project |
| **Archive** | Hide the conversation from the main list |
| **Duplicate** | Create a copy of the session |
| **Delete** | Permanently remove the session |

Use the search bar at the top of the chat sidebar to filter conversations by name.

### Project filtering

Use the **project selector** dropdown at the top of the sidebar to filter all panels (chats, agents, skills) by project. Selecting **All** shows everything; **Unassigned** shows items without a project.

---

## Agents

The Agents panel manages AI agent profiles.

### Viewing agents

1. Click the **Agents** icon in the rail
2. The sidebar lists all agent profiles
3. Click a profile to open its detail view in the main panel

### Creating an agent

1. Click **+ New** at the top of the agents sidebar
2. A create form opens in the main panel with fields: name, extends (parent agent), model, reasoning effort, max turns, max unattended turns, and description / system prompt
3. On save, an `agent.md` file is written to `.agentone/agents/<name>/`, the manifest loader reloads all agents, and the new agent detail view opens
4. Agent definitions can also be created by placing `agent.md` files directly in `.agentone/agents/`

### Agent details

The agent detail view shows:
- **Name** — unique identifier
- **Model** — the LLM model assigned (e.g., `gemma4:26b`)
- **Tools** — tool groups available to this agent
- **Skills** — skills the agent has loaded
- **Subagents** — agents this agent can delegate to
- **Settings** — reasoning effort, scheduler strategy, token limits, etc.
- **Versions** — history of agent definition changes

### Agent hierarchy

Agents can inherit from other agents. The **baseagent** provides core task capabilities. Custom agents extend it to add tools, skills, and subagents. Settings cascade through the inheritance chain — a child agent inherits its parent's settings unless overridden.

---

## Skills

The Skills panel lists installed skill definitions.

### Viewing skills

1. Click the **Skills** icon in the rail
2. The sidebar shows all skills with a search bar
3. Click a skill to view its details: name, slug, description, tool description, and auth requirements

### Loading skills

Skills are loaded from skill definitions in the system. They can be installed from repositories or defined locally in `.agentone/skills/`.

---

## Projects

Projects group agents, skills, and sessions together.

### Viewing projects

1. Click the **Projects** icon in the rail
2. The sidebar lists all projects
3. Click a project to view its details

### Creating a project

1. Click **+ New** at the top of the projects sidebar
2. A create form opens: enter a name, description, and optional filesystem path
3. On save, the project directory is created with a `.agentone/project.md` manifest, the project is registered in `.agentone/projects.yaml`, the manifest loader reloads, and the project detail view opens
4. The project immediately appears in the project selector dropdown

### Project filtering

Once projects exist, use the **project selector** at the top of the sidebar to filter all panels. This is useful when working with multiple independent agent configurations.

---

## Workspaces

Workspaces provide file system context for sessions.

### Viewing workspaces

1. Click the **Workspaces** icon in the rail (it may be under the "Spaces" icon)
2. The sidebar lists all workspaces
3. Click a workspace to view its path and details

### Creating a workspace

1. Click **+ New** at the top of the workspaces sidebar
2. Enter a name, description, and filesystem path

### Workspace in sessions

When a session is bound to a workspace, the right panel's **Workspace** tab shows the workspace files and structure.

---

## Cron jobs

Schedule automated tasks for agents.

### Viewing cron jobs

1. Click the **Cron** icon in the rail
2. The sidebar lists all scheduled jobs with their status and next run time

### Creating a cron job

1. Click **+ New** in the cron sidebar
2. Configure:
   - **Name** — job identifier
   - **Schedule** — cron expression (e.g., `0 * * * *` for hourly)
   - **Agent** — target agent
   - **Session mode** — `new` (create a fresh session each run) or `existing`
   - **Message** — the message to send to the agent

### Job status

Each cron job shows:
- **Status** — last run result
- **Next run** — scheduled time
- **Total runs** — execution count

---

## Data flows (streams &amp; sets)

Data flows replace the legacy named-pipe system. A flow is a `DataCollection`
that collects outputs from agent task calls (via a *query* source) and optionally
chains them through downstream flows (via *stream* or *set* sources).

**Streams** are append-only logs — every matching call produces an item.
**Ordered sets** are mutable collections with deduplication — if a call produces
the same *member* as an existing item, the item is updated rather than duplicated.

### Viewing data flows

1. Click the **Data flows** icon in the rail
2. The sidebar lists all data flows, showing type (Stream / Ordered Set) and item count

### Creating a data flow

1. Click **+ New** in the data flows sidebar
2. Give it a **Name** and select the **Type** (Stream or Ordered Set)
3. Configure **Sources** — see below
4. Configure **Processor** — the agent and function that transforms incoming data into items
5. For ordered sets: configure **Member/Score fields** and optional **On-removed handler**
6. Set **Reprocess** limits if desired

### Source configuration

Each flow can have multiple sources. Click **Add source** to add one, then choose the type:

**Query source** — matches completed `AgentTaskCall` records:

| Field | Description |
|---|---|
| Project | Filter by project (optional) |
| Agent | Agent name(s) — one or more, glob patterns supported |
| Function | Task function name(s) — one or more, glob patterns supported |
| Session | Session name(s) — one or more (optional) |

**Stream source** — sources items from another stream by name.

**Set source** — sources items from another ordered set by name.

Multi-value fields (agent, function, session) use tag chips — type or select from the dropdown to add values, click the ✕ on a chip to remove. The dropdown hides already-selected options.

### Processor configuration

| Field | Description |
|---|---|
| Agent | The agent whose task will process incoming data |
| Function | The task function to run — filtered to show only tasks available on the selected agent |
| Session | Optional session name template (`{source_agent.name}` is substituted) |

Each matching source call triggers the processor function with the call's result as input. The processor's return value becomes the collection item.

### Ordered set fields

Shown only when **Type = Ordered Set**:

| Field | Description |
|---|---|
| Member field | Python expression to extract the dedup key (e.g., `result.id`) |
| Score field | Python expression for the ordering score (e.g., `result.priority`) |
| On-removed agent | Agent for the removal handler task |
| On-removed function | Task function to fire when an item is removed from the set |

### Reprocess settings

| Field | Description |
|---|---|
| Retroactive on source change | Max items to reprocess when source filters are edited (0 = off) |
| Max reprocess | Max items to reprocess when the processor is updated (0 = off) |

### Derived flows

In the data flow detail view, a **Derived flows** card lists any flows that source from this one (via stream or set source). This makes it easy to see the cascade: changing a source flow affects everything downstream.

### Recent items

The detail view also shows the most recent items in the flow (caller, member, score, value, and timestamp) for quick inspection.

---

## Settings

The Settings panel has six sub-panels, accessible from the gear icon in the rail.

### Conversation

Configure conversation defaults:
- Model selection
- Reasoning effort (none to xhigh)
- Precision/temperature (precise to experimental)
- Max turns, retries, history messages
- Scheduler strategy (interrupt, queue, merge, parallel)
- Tool call syntax

### Appearance

Choose a color skin:
- **Default** — gold/warm tones
- **Ares** — red
- **Mono** — gray
- **Slate** — blue-gray
- **Poseidon** — ocean blue
- **Sisyphus** — purple
- **Charizard** — orange
- **Sienna** — warm clay/sand

Toggle between **light** and **dark** mode. Adjust **font size** (small, default, large).

### Preferences

Configure:
- Allow/deny lists for commands, tasks, tools, skills, and subagents (wildcards supported)
- Subagent result delivery mode (passive or immediate)
- Extra settings (JSON key-value pairs)

### Providers

Manage LLM provider connections:

1. **API Providers** — add provider URLs (e.g., OpenAI, Ollama, custom endpoints)
2. **AI Models** — configure models per provider (name, context length, vision support, rate limits)
3. **API Keys** — add API keys per provider with per-key rate limits

Rate limits can be set at three levels:
- **Provider** — parallel call limit
- **Model** — requests/day, requests/min, tokens/day, tokens/min, parallel calls
- **API Key** — requests/day, requests/min, tokens/day, tokens/min

### System

Configure:
- Password/authentication settings
- System-level preferences

### Plugins

Manage plugin integrations (if any are installed).

---

## Insights

The Insights panel opens a **Dashboard** showing system health and metrics:
- Agent counts and status
- Active sessions
- Recent activity
- System resource usage

---

## Log viewer

The Logs panel provides a log viewer:

1. Click the **Logs** icon in the rail
2. Select a log file from the dropdown (agent logs, errors, gateway)
3. Configure:
   - **Tail count** — number of recent lines to show
   - **Auto-refresh** — periodically fetch new lines
   - **Wrap** — toggle line wrapping
   - **Copy all** — copy entire log to clipboard

---

## Memory

The Memory panel (if available) provides a view into the agent's personal memory storage.

---

## Todos

The Todos panel shows the current task list for the active session.

---

## Drag-to-resize panels

The sidebar and right panel can be resized by dragging their edges:

1. Hover over the right edge of the sidebar or the left edge of the right panel
2. When the cursor changes to a resize cursor, click and drag
3. Release to set the new width

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message (in chat composer) |
| `Shift+Enter` | New line (in chat composer) |

---

## Troubleshooting

### Chat is not responding

1. Check that the Celery worker is running (`celery -A config worker -l INFO`)
2. Check that the Celery beat scheduler is running (`celery -A config beat -l INFO`)
3. Verify Redis is running at `localhost:6379`
4. Check the browser console for WebSocket errors
5. If the WebSocket disconnects, it will auto-reconnect within 2 seconds

### No agents appear

Agent definitions are loaded from `.agentone/agents/` directory. Ensure:
- The manifest files exist with valid YAML frontmatter
- The loader has been run (save an agent in the admin or restart the server)
- The database and Redis are accessible

### Settings changes have no effect

Some settings only apply to new sessions, not existing ones. Check if the setting supports live updates or requires a new session version.

### Sidebar panel is empty

1. Check the project selector — it may be filtering items
2. Try switching to **All** in the project selector
3. Check if the selected panel has any data (agents, sessions, etc.)

---

**See also:** [Architecture](architecture.md) · [Development guide](development.md) · [Manifest format](manifest-format.md)
