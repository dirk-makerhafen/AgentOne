---
name: agentone-admin
description: >
  Create and update AgentOne YAML manifest files: agent.md, scripts.md,
  skill.md, stream.md, set.md, cron.md, and project.md.
---

# Manifest Administration Skill

You can create and update all AgentOne YAML manifest files.
**How to use this skill:** Read the section for the manifest type you want
to create/update (agent.md, scripts.md, etc.), then use your
`filesystem-write.*` tools to write the file directly. After creating or
editing manifests, run `python3 manage.py reload_all .` to sync them to
the database.

Below is the complete reference for every manifest format.

---

## agent.md — Agent Declaration

Location: `.agentone/agents/<name>/agent.md`

### YAML Frontmatter

```yaml
---
name: <name>               # required — unique agent name
oldName: <name>            # optional — previous name (for rename)
model: <model>             # required — e.g. gemma4:26b
description: <text>        # optional — short description (used as system prompt)
extends: <parent>          # optional — parent agent name(s)
subagents:
  - <name>                 # simple string, or dict:
  - name: <name>
    create: agent          # auto | agent | user | both
    lifecycle: single      # single | multi | background
    visibleTo: both        # agent | user | both
    maxTurns: 0            # 0 = unlimited

tools: [<names>]           # allowed tools
disallowedTools: []
tasks: [<names>]           # allowed tasks
disallowedTasks: []
commands: [<names>]        # allowed commands
disallowedCommands: []
skills: [<names>]          # allowed skills
disallowedSkills: []

maxRetries: 0
maxTurns: 0                # 0 = unlimited
maxUnattendedTurns: 0
maxHistoryMessages: 0
reasoningEffort: medium    # none | minimal | low | medium | high | xhigh
schedulerStrategy: queue   # interrupt | queue | merge | parallel
toolCallSyntax: default
priority: 0                # 0 = highest
thinking: false
task_prompt: <text>        # optional custom task prompt
---
<Markdown body — used as system prompt>
```

### Tools List Syntax

Use `+` prefix to extend (inherit + add), and `.*` suffix for wildcards:

```yaml
tools: [+, filesystem-read.*, filesystem-write.*, web.*]
```

This means: inherit all baseagent tools, then add all filesystem-read,
filesystem-write, and web tools.

### Subagent Create Modes

| Mode     | Who creates                             |
|----------|-----------------------------------------|
| `auto`   | System, on parent session start         |
| `agent`  | Parent AI during execution              |
| `user`   | User explicitly                         |
| `both`   | Either                                  |

### Subagent Lifecycle Modes

| Mode         | Session strategy        | History                          |
|--------------|-------------------------|----------------------------------|
| `single`     | One session per parent  | Fresh chain per delegation       |
| `multi`      | Dedicated per relation  | Full history, persists           |
| `background` | Dedicated, async        | Full history, non-blocking       |

### Resolution Precedence

Tool/task/command names resolved in this order:
1. Agent's own defined_*versions (from its `scripts/` directory)
2. Extends chain (parent agents' versions)
3. Global (no parent_agent, no parent_project, no parent_skill)

---

## scripts.md — Task/Tool/Command Manifest

Location: alongside Python files in a `scripts/` directory.

### Structure

```yaml
---
group: <name>              # optional — namespace group

tasks:                     # section heading = task_type
  - name: <name>           # required — unique within section
    type: python           # python | chain | group | map | script
    file: <path>           # Python file (relative to scripts.md)
    function: <name>       # function name within file
    bound: True            # True = first arg receives Session

  - name: <name>
    type: chain
    chain:                 # ordered list of step names
      - step1
      - step2

  - name: <name>
    type: group            # runs children in parallel
    group:
      - child1
      - child2

  - name: <name>
    type: map              # producer → list, consumer called per item
    map:
      - producer
      - consumer

tools:
  - name: <name>
    file: <path>
    function: <name>
    bound: False
    requires_approval: false
    max_retries: 2
    retry_delay: 5
    priority: 5

commands:
  - name: <name>
    file: <path>
    function: <name>
    bound: True
    trigger: <name>        # slash command trigger (without /)
---
```

### Execution Modes (`type`)

| Mode     | Behavior                                                   |
|----------|------------------------------------------------------------|
| python   | Calls a Python function via importlib                      |
| chain    | Runs children sequentially, each receives previous output  |
| group    | Runs children in parallel                                  |
| map      | Producer yields list, consumer called per item (parallel)  |
| script   | Runs arbitrary executable (use `script:` key, not file+function) |

### Section Headings

| Heading   | TaskType | Purpose                        |
|-----------|----------|--------------------------------|
| `tasks:`  | TASK     | Internal business logic        |
| `tools:`  | TOOL     | LLM-callable functions         |
| `commands:`| COMMAND | User-triggered (/commands)     |

### SCRIPT Mode

```yaml
- name: deploy
  script: deploy.sh
  description: Deploy the application
```

Runtime: CLI args passed as positional args; kwargs serialised as JSON on
stdin; stdout returned (parsed as JSON if valid).

---

## skill.md — Skill Declaration

Location: `.agentone/skills/<name>/skill.md`

```yaml
---
name: <name>
description: <text>
---
<Skill description / instructions — injected into agent context when loaded>
```

Skills can have their own `scripts/` directory with `scripts.md` for
skill-specific tools.

---

## stream.md / set.md — Data Flow Definition

Location: `.agentone/streams/<name>.md` or `.agentone/sets/<name>.md`

The directory determines the type: `streams/` → append-only stream (auto
member/score), `sets/` → mutable ordered set (user-defined member/score).

### YAML Frontmatter Fields

| Field                          | Required | Type   | Default | Description                                       |
|--------------------------------|----------|--------|---------|---------------------------------------------------|
| `name`                         | yes      | string | —       | Collection name (unique)                          |
| `description`                  | no       | string | ""      | Human-readable description                        |
| `sources`                      | yes      | list   | []      | Source definitions (see below)                    |
| `processor`                    | yes      | dict   | {}      | Agent + function that transforms items            |
| `processor.agent`              | yes      | string | —       | Agent name for the processor task                 |
| `processor.function`           | yes      | string | —       | Task function name                                |
| `processor.session`            | no       | string | default | Session name (supports {source_agent.name} template) |
| `on_removed`                   | no       | dict   | {}      | Handler fired when a set item is removed          |
| `on_removed.agent`             | yes      | string | —       | Agent for the removal handler                     |
| `on_removed.function`          | yes      | string | —       | Task function for the removal handler             |
| `member_field`                 | no       | string | ""      | Python eval expression for set member (sets only) |
| `score_field`                  | no       | string | ""      | Python eval expression for set score (sets only)  |
| `retroactive_on_source_change` | no       | int    | 0       | Max items to reprocess when sources change        |
| `max_reprocess`                | no       | int    | 0       | Max items to reprocess on processor update        |

### Source Definitions

| Type    | Extra fields                                | Behaviour                                        |
|---------|---------------------------------------------|--------------------------------------------------|
| query   | project, agent, session, function (glob)    | Match completed AgentTaskCall records             |
| stream  | stream: "<name>"                            | Source from another stream's items                |
| set     | set: "<name>"                               | Source from another set's items                   |

### Example: Stream

```yaml
---
name: health_events
sources:
  - type: query
    agent: [collector]
    function: [check_health]
processor:
  agent: reporter
  function: parse_event
---
```

### Example: Ordered Set with on_removed

```yaml
---
name: alert_report
sources:
  - type: stream
    stream: health_events
processor:
  agent: reporter
  function: generate_report
member_field: item.source_call.pk
score_field: item.score
on_removed:
  agent: reporter
  function: alert_removed
---
```

---

## cron.md — Cron Job Declaration

Location: `.agentone/cronjobs/<name>.md`

```yaml
---
name: <name>               # required — unique cron job name
description: <text>        # optional
schedule: "0 8 * * *"      # required — standard cron expression
agent: <name>              # required — target agent
is_active: true            # default: true
session_mode: new          # new | existing
session_name: ""           # session name for existing mode
message: "<text>"          # message text
function_type: ""          # task | tool | command | "" (send message)
function_name: ""
---
```

Cron jobs created/edited through the UI auto-sync to `.agentone/cronjobs/<name>.md`.
Removing a file and reloading archives the record (preserves tracking data).

---

## project.md — Project Declaration

Location: `.agentone/project.md` at project root

```yaml
---
name: <name>               # required — unique project name
workspaces:
  - name: <name>           # required — unique workspace name
    path: <path>           # required — absolute or relative to project root
    description: <text>    # optional
---
<Project description body>
```

Projects are referenced in `.agentone/projects.yaml` (YAML list of directory
paths).

---

## Filesystem Layout

```
.agentone/
├── agents/                     # Global agents
│   ├── <name>/
│   │   ├── agent.md
│   │   ├── scripts/
│   │   │   ├── scripts.md
│   │   │   └── *.py
│   │   └── agents/             # Nested subagents
│   │       └── <child>/
│   │           └── agent.md
├── cronjobs/                   # Global cron jobs
│   └── <name>.md
├── scripts/                    # Global scripts (available to all agents)
│   ├── scripts.md
│   ├── *.py
│   └── <subdir>/
│       ├── scripts.md
│       └── *.py
├── sets/                       # Ordered set data flows
│   └── <name>.md
├── skills/                     # Global skills
│   └── <name>/
│       ├── skill.md
│       └── scripts/
│           ├── scripts.md
│           └── *.py
├── streams/                    # Append-only stream data flows
│   └── <name>.md
└── projects.yaml               # Project references
```