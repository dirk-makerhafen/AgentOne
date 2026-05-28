# Manifest Format Reference

AgentOne uses YAML manifest files to declare agents, skills, tasks, tools, and commands. These manifests live under `.agentone/` directories.

---

## `agent.md` — Agent Declaration

Declares an agent. Lives at `.agentone/agents/<name>/agent.md`.

### YAML Frontmatter

```yaml
---
name: myagent                   # required — unique agent name
oldName: previous_name          # optional — renames an existing agent
model: gemma4:26b               # required — AI model identifier

description: A helpful agent    # used as system prompt (from content body)

extends: baseagent              # optional — comma-separated or list of parent agent names
subagents:                      # optional — names of child subagents with metadata
  - file_operator
  - name: code_reviewer
    create: user                # auto | agent | user | both (default: agent)
    lifecycle: single           # single | multi | background (default: single)
    visibleTo: both             # agent | user | both (default: both)
    maxTurns: 10                # 0 = unlimited (default: 0)

tools: [read, write, edit]     # allowed tool names
disallowedTools: []            # denied tool names
tasks: [process_turn, ...]     # allowed task names
disallowedTasks: []            # denied task names
commands: [ping]               # allowed command names
disallowedCommands: []         # denied command names
skills: [my_skill]             # allowed skill names
disallowedSkills: []           # denied skill names

maxRetries: 0                  # max retry attempts
maxTurns: 0                    # max conversation turns (0 = unlimited)
maxUnattendedTurns: 0          # max autonomous turns
maxHistoryMessages: 0          # max stored messages
reasoningEffort: medium        # none | minimal | low | medium | high | xhigh
schedulerStrategy: queue       # interrupt | queue | merge | parallel
toolCallSyntax: default        # default | custom
priority: 0                    # 0 = highest
thinking: false                # enable thinking tokens

task_prompt: optional text     # custom task prompt
---
Agent body content goes here — used as the system prompt.
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | string | Unique agent name within its parent scope |
| `oldName` | string | Previous name for migration (renames agent model) |
| `model` | string | AI model identifier (e.g. `gemma4:26b`) |
| `extends` | list | Parent agent name(s) for property/method inheritance |
| `subagents` | list | Named subagent references (see [Subagent Entry](#subagent-entry)) |
| `tools`/`tasks`/`commands`/`skills` | list | Allow-listed item names |
| `disallowed*` | list | Denied item names |
| Priority/scheduling | various | Execution control knobs |

### Subagent Entry

Each entry in `subagents:` can be a simple string name or a dict with metadata:

```yaml
subagents:
  - file_operator                  # simple name (defaults apply)
  - name: code_reviewer
    create: user                   # who can create: auto | agent | user | both
    lifecycle: single              # single | multi | background
    visibleTo: both                # visibility: agent | user | both
    maxTurns: 10                   # max conversation turns (0 = unlimited)
```

**`create` modes:**
| Mode | Who creates | Example |
|---|---|---|
| `auto` | System, on parent session start | Always-on utility agent |
| `agent` | Parent AI during execution | Delegate research task |
| `user` | User explicitly | Start a code review session |
| `both` | Either | General-purpose assistant |

**`lifecycle` modes:**
| Mode | Session Strategy | History |
|---|---|---|
| `single` | One session per parent, shared | Fresh chain per delegation |
| `multi` | Dedicated session per relationship | Full history, persists until `session_end()` |
| `background` | Dedicated session, async | Full history, parent doesn't block |

### Resolution Precedence

Tool/task/command names are resolved in this order:
1. Agent's own `defined_*versions` (from its `scripts/` directory)
2. Extends chain (parent agents' versions)
3. Global (no parent_agent, no parent_project, no parent_skill)

---

## `scripts.md` — Task/Tool/Command Manifest

Declares executable entries for a folder. Lives alongside Python files in a `scripts/` directory.

### YAML Structure

```yaml
---
tasks:                                  # section heading = task_type
  - name: process_turn                  # unique name within scope
    type: chain                         # python | chain | group | script
    chain:                              # only for type: chain
      - build_llm_context
      - call_llm
      - parse_llm_response
      - ingest_assistant_message
      - decide_next_step

  - name: ingest_user_message
    file: ingest_user_message.py        # Python file to load
    function: ingest_user_message       # function name within that file
    bound: True                         # True = first arg receives session

  - name: search_then_analyze
    type: group                         # runs child items in parallel
    group:
      - web_search
      - file_search

tools:
  - name: delegate_task
    file: delegate_task.py
    function: delegate_task
    bound: True

  - name: read
    file: read.py
    function: read
    bound: False
    requires_approval: false            # optional
    max_retries: 2                      # optional
    retry_delay: 5                      # optional (seconds)
    priority: 5                         # optional (0 = highest)

commands:
  - name: ping
    file: ping.py
    function: ping
    bound: True
    trigger: ping                       # optional — slash command trigger
---
```

### Entry Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `name` | yes | string | Unique entry name within its section |
| `type` | no | string | Execution mode: `python` (default), `chain`, `group`, `script` |
| `file` | for `python` type | string | Path to Python file (relative to scripts.md) |
| `function` | for `python` type | string | Function name within the file |
| `bound` | no | bool | `True` = first argument receives the Session object |
| `chain` | for `chain` type | list | Ordered list of step names to execute sequentially |
| `group` | for `group` type | list | Step names to execute in parallel |
| `trigger` | no | string | Slash command trigger (e.g. `ping` for `/ping`) |
| `requires_approval` | no | bool | Whether human approval is required |
| `max_retries` | no | int | Max retry attempts |
| `retry_delay` | no | int | Delay between retries (seconds) |
| `priority` | no | int | Execution priority (0 = highest) |

### Section Headings

Each top-level key defines the `task_type` for all entries within:

| Heading | `TaskType` | Purpose |
|---|---|---|
| `tasks:` | TASK | Internal business logic (chains, pipelines) |
| `tools:` | TOOL | LLM-callable functions (tools the AI invokes) |
| `commands:` | COMMAND | User-triggered commands (e.g. `/ping`) |

### Execution Modes (`type`)

| Mode | `task_execution_mode` | Behavior |
|---|---|---|
| `python` (default) | FUNCTION | Calls a Python function via `importlib` |
| `chain` | CHAIN | Runs child steps sequentially, each receives previous output |
| `group` | GROUP | Runs child steps in parallel, joins on completion |
| `script` | SCRIPT | Runs a script file |

### Chain/Group Children

For `type: chain` and `type: group`, child steps are named entries that must exist in the same `scripts.md` or in an ancestor's scripts:

```yaml
tasks:
  - name: research_pipeline
    type: chain
    chain:
      - web_search
      - summarize_results
      - generate_report

  - name: web_search
    file: search.py
    function: web_search
    bound: True

  - name: summarize_results
    file: summarize.py
    function: summarize
    bound: True

  - name: generate_report
    file: report.py
    function: generate_report
    bound: True
```

The chain steps' child relationships are stored as `SortedManyToManyField("self")` on `TaskDefinitionVersion.child_tasks`.

---

## `skill.md` — Skill Declaration

Declares a skill (capability bundle). Lives at `.agentone/skills/<name>/skill.md`.

```yaml
---
name: my_skill
description: A reusable skill bundle
---
Skill description / content.
```

Skills follow the same `scripts/` pattern: a `skills/<name>/scripts/scripts.md` declares the skill's tasks, tools, and commands.

---

## `cron.md` — Cron Job Declaration

Declares a scheduled cron job. Lives at `.agentone/cronjobs/<name>.md`.
Jobs can be global (no `parent_project`) or per-project.

```yaml
---
name: daily-digest
description: Send daily summary at 8am
schedule: "0 8 * * *"              # standard cron expression
agent: baseagent                    # target agent (resolved by name)
is_active: true                     # default: true
session_mode: new                   # new | existing
session_name: ""                    # session name for existing mode
message: "Provide a summary"        # message text (stored as GenericContent)
function_type: ""                   # task | tool | command | "" (send message)
function_name: ""
pipe_names: []                      # published to these named pipes after run
---
```

Cron jobs created or edited through the UI are automatically written to
`.agentone/cronjobs/<name>.md` so they stay in sync with the file system.
Deleting a cron job in the UI removes the corresponding file.

When the loader runs (`reload_all`), cron jobs are upserted by
`(parent_project, name)` — re-running updates the schedule, message, agent,
or other fields in place.

Removing a `cron.md` file and re-running the loader **archives** the
corresponding record (`is_archived=True`) rather than deleting it, so
tracking data (run count, last run time, etc.) is preserved.  Archived
crons are hidden from the default sidebar view but can be viewed by
switching to the "Archived" tab in the cron panel.

---

## `project.md` — Project Declaration

Declares a project with optional workspace definitions. Lives at `.agentone/project.md` at the root of a project folder.

Each project folder is referenced in `.agentone/projects.yaml` (a YAML list of directory paths).

```yaml
---
name: my-project
workspaces:
  - name: Workspace name
    path: some/path/relative/to/project/root
    description: some description
  - name: other workspace
    path: /absolute/path
    description: foobar
---
Project description body goes here.
```

### Frontmatter Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `name` | yes | string | Unique project name |
| `workspaces` | no | list | List of workspace definitions (see [Workspace Entry](#workspace-entry)) |

The markdown body (after the frontmatter) is used as the project's `description`.

### Workspace Entry

Each entry in the `workspaces:` list is a dict with:

| Field | Required | Type | Description |
|---|---|---|---|
| `name` | yes | string | Unique workspace name |
| `path` | yes | string | Filesystem path; absolute paths used as-is, relative paths resolved against the project root |
| `description` | no | string | Optional description of the workspace |

When the project is loaded (via `reload_all`), each workspace is created or updated as a `WorkspaceModel` record. Relative paths are resolved relative to the project folder containing `.agentone/`. Workspaces are available for selection in cron jobs, session workspaces, and the workspace sidebar.

---

## Filesystem Layout

```
.agentone/
├── cronjobs/                   # Global cron jobs (no parent_project)
│   └── <name>.md
├── scripts/                    # Global scripts (available to all agents)
│   ├── scripts.md
│   ├── python.py
│   ├── shell.py
│   └── ...
├── skills/                     # Global skills
│   └── <skill>/
│       ├── skill.md
│       └── scripts/
│           ├── scripts.md
│           └── ...
├── agents/                     # Global agents
│   ├── baseagent/
│   │   ├── agent.md
│   │   ├── scripts/
│   │   │   ├── scripts.md
│   │   │   └── *.py
│   │   └── agents/             # Nested subagents
│   │       └── <child>/
│   │           └── agent.md
│   └── agentone/
│       ├── agent.md
│       └── scripts/
│           └── scripts.md
└── projects.yaml               # Project references
```

### Key Rules

1. **`scripts.md`** is the single source of truth — no `@tool()`/`@task()` decorators
2. Manifests are pure YAML with opening `---` but no closing `---`
3. Python files are loaded via `importlib`, never `exec()`
4. Version identifiers are **git tree SHAs** from install repos at ``~/.agentone/install/`` (one per scope: global + per-project). Tree SHAs are deterministic — same content always produces the same hash.
5. Versioned models (`AgentVersionModel`, `TaskDefinitionVersion`, etc.) are immutable — `save()` raises `ValidationError` if `pk` exists

---

## Reload Process

`python3 manage.py reload_all .` triggers:

1. **Sync — copy sources into install repos:**
   - Global: ``rsync .agentone/ → ~/.agentone/install/global/``
   - Per-project: ``rsync project/.agentone/ → ~/.agentone/install/project_<name>/``
   - ``git add -A && git commit`` (only if dirty) in each install repo

2. **Pass 1 — Create models:**
    - Load global ``scripts/`` → create ``TaskDefinition`` + ``TaskDefinitionVersion``
    - Load global ``skills/`` → create ``SkillModel`` + ``SkillModelVersion``
    - Load global ``agents/`` → recursively create ``AgentModel`` + ``AgentVersionModel`` (with ``defined_*versions`` for scripts, skills, subagents)
    - Load global ``cronjobs/`` → upsert ``Cronjob`` by ``name``
    - For each project in ``projects.yaml``, repeat (same steps + cronjobs/ per project)
   - Version identifiers are **git tree SHAs** computed via ``git rev-parse HEAD:{relative_path}`` for each manifest folder

3. **During Pass 1 (per-agent):**
   - Resolve tool/task/command name lists into ``task_versions`` M2M
   - Resolve subagent name lists into ``subagent_versions`` M2M
   - Store ``subagent_configs`` JSON with per-entry metadata

4. **Version detection:** Each manifest folder's tree SHA is deterministic — identical files produce the same SHA across different commits. ``get_or_create`` finds the existing version record when nothing changed. Agent versions additionally compute a ``content_hash`` from all dependency PKs to catch cascading changes.
