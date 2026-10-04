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

access:                        # optional — filesystem access policy (see below)
  workspace:
    write:
      default: deny
  external:
    read:
      default: deny
      allow: ["~/shared/**"]
    write:
      default: deny

maxRetries: 0                  # max retry attempts
maxTurns: 0                    # max conversation turns (0 = unlimited)
maxUnattendedTurns: 0          # max autonomous turns
maxHistoryMessages: 0          # max stored messages
loadGuidanceFileIndex: true    # list nested guidance files (AGENTS.md/CLAUDE.md) not already loaded
guidanceFileIndexLimit: 10         # max nested guidance files listed in the index (0 = omit index)
autoload:                      # optional — AGENTS.md autoload (see below)
  files: [AGENTS.md]           # workspace-relative patterns (*, **, ?); bare name = root only
  maxFiles: 10                 # max files pinned into context
  maxChars: 32768              # total char budget (0 = disable contents)
  maxCharsPerFile: 8192        # per-file char cap (remainder truncated with marker)
autoCompactLimit: 100000        # token threshold for auto-compaction (0 = disabled)
autoCompactKeepPercent: 15     # percentage of newest tokens to keep in full on compaction (0 = compact everything)
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
| `access` | dict | Filesystem access policy (see [Access Policy](#access-policy)) |
| `autoload` | dict | AGENTS.md autoload (see [Autoload](#autoload)) |
| `loadGuidanceFileIndex` | bool | Nested guidance-file index toggle (default false — opt-in) |
| `guidanceFileIndexLimit` | int | Max nested guidance files listed in the index (default 10, 0 = omit) |
| Priority/scheduling | various | Execution control knobs |

### Access Policy

The `access:` block defines a filesystem access policy for filesystem, shell,
and Python tools. It has two scopes:

- **`workspace`** — overrides the rules *inside* the workspace (see
  [project.md workspace entry](#workspace-entry) for the base rules). Patterns
  must be workspace-relative (no leading `/`, no `..`, no `~`).
- **`external`** — rules for paths *outside* the workspace. Patterns must be
  absolute or `~`-anchored. When unset, external `default` falls back to `deny`.

Each scope holds `read:` and `write:` actions, and each action is a dict with
`default` (`allow` | `ask` | `deny`) and per-path pattern lists (`allow`,
`ask`, `deny`). Glob patterns use `*`, `**`, and `?` (e.g. `**/*.env`).

Precedence per action: `deny` > `ask` > `allow` > `default`. Deny patterns from
any scope apply globally. `write` implies `read` on allowed/asked paths; `read`
rules never grant writes.

```yaml
access:
  workspace:
    write:                     # tighten workspace write rules for this agent
      default: deny            # read-only workspace from this agent's perspective
  external:
    read:
      default: deny
      allow: ["~/shared/**"]   # a shared directory outside the workspace
    write:
      default: deny            # external writes blocked by default
      allow: ["/tmp/work/**"]
```

### Autoload

The `autoload:` block names workspace files to pin into the session's
first user messages (see `docs/agents-md.md`). It inherits through
`extends` and is session-overridable like every other agent setting.

```yaml
autoload:
  files: [AGENTS.md, "docs/*.md", "**/loadmeall.file"]
  maxFiles: 10
  maxChars: 32768
  maxCharsPerFile: 8192
```

Pattern rules (workspace-relative, files only):

- Bare filenames (`AGENTS.md`) match at the workspace root only —
  use `**/` for recursion (`**/AGENTS.md`).
- `*` / `?` never cross `/`; `**` crosses directories.
- Config order is priority order (decides what survives the caps).
- No leading `/`, no `~`, no `..` (rejected at load); matches outside
  the workspace (symlink escapes) and policy-denied files are skipped.
- `maxChars: 0` disables contents; over-budget files are truncated with
  a `[truncated …]` marker. Counts are chars, not tokens.

The nested guidance-file index is a separate feature controlled by the
standalone `loadGuidanceFileIndex` key (default `false` — opt-in) and capped by
`guidanceFileIndexLimit` (default 10, `0` omits the index message). It lists
nested `AGENTS.md`/`CLAUDE.md` files *not* already pinned by `autoload:`
— the two never duplicate each other — and touching a listed subtree
produces a one-line read hint. Either feature works without the other:
with contents disabled (`maxChars: 0`) the index lists everything,
including the root file.

### Subagent Entry

Each entry in `subagents:` can be a simple string name or a dict with metadata:

```yaml
subagents:
  - file_operator                  # simple name (defaults apply)
  - name: code_reviewer
    create: user                   # who can create: auto | agent | user | both
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
    type: chain                         # python | chain | group | map | script
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

  - name: process_new_emails
    type: map                           # maps a list over a function
    map:
      - sync_account                    #   child[0]: produces a list
      - new_email                       #   child[1]: called per item

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

  - name: deploy
    script: deploy.sh                   # arbitrary executable (SCRIPT mode)
    description: Deploy the application
---
```

### Entry Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `name` | yes | string | Unique entry name within its section |
| `type` | no | string | Execution mode: `python` (default), `chain`, `group`, `map`, `script` |
| `file` | for `python` type | string | Path to Python file (relative to scripts.md) |
| `function` | for `python` type | string | Function name within the file |
| `bound` | no | bool | `True` = first argument receives the Session object |
| `chain` | for `chain` type | list | Ordered list of step names to execute sequentially |
| `group` | for `group` type | list | Step names to execute in parallel |
| `map` | for `map` type | list | Exactly 2 step names: `[producer, consumer]` — producer yields a list, consumer is called per item |
| `script` | for `script` type | string | Path to executable (relative to scripts.md) — replaces `file` / `function` |
| `trigger` | no | string | Slash command trigger (e.g. `ping` for `/ping`) |
| `access` | no | `read` \| `write` | Filesystem posture for workspace access enforcement — see [Filesystem Access Posture](#filesystem-access-posture) |
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
|---|---|---|---|
| `python` (default) | FUNCTION | Calls a Python function via `importlib` |
| `chain` | CHAIN | Runs child steps sequentially, each receives previous output |
| `group` | GROUP | Runs child steps in parallel, joins on completion |
| `map` | MAP | Runs child[0] (producer) to get a list, then calls child[1] (consumer) per item in parallel |
| `script` | SCRIPT | Runs a script file |

### Filesystem Access Posture

The optional `access:` field on a scripts.md entry classifies the tool's
filesystem posture for workspace access enforcement. It takes exactly one of
two values:

| Value | Meaning |
|---|---|
| `read` | The tool only reads files; its absolute-path arguments are treated as reads |
| `write` | The tool can create/modify/delete files; its absolute-path arguments are treated as writes |

```yaml
tools:
  - name: read
    file: read.py
    function: read
    access: read      # classified as a read-only filesystem tool

  - name: edit
    file: edit.py
    function: edit
    access: write     # classified as a write-capable filesystem tool
```

This posture drives three enforcement layers:

1. **Scheduler** — when a call is dispatched, its absolute-path arguments are
   evaluated against the workspace access policy and may set
   `requires_approval` (see [Access Policy](#access-policy)).
2. **Execution** — `BoundTask` hard-blocks any call whose path arguments (or
   shell/python source) are denied by the policy.
3. **Shell/python source analysis** — for `shell` / `python` tools, `read`
   posture uses a read-only command whitelist; anything not whitelisted (or
   any in-place write flag such as `sed -i` / `sort -o` / `perl -i`) is
   treated as write-capable (fail-safe).

The posture is persisted as `TaskDefinition.access_posture`. When `access:` is
omitted, the posture is inferred from the legacy `group:` convention
(`filesystem-read` → `read`, `filesystem-write` → `write`); tools in other
groups are not filesystem-guarded.

### Chain/Group/Map Children

For `type: chain`, `type: group`, and `type: map`, child steps are named entries that must exist in the same `scripts.md` or in an ancestor's scripts:

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

  - name: process_new_emails
    type: map
    map:
      - sync_account       # producer — runs first, returns a list
      - new_email          # consumer — called once per item in parallel
```

The child relationships are stored as `SortedManyToManyField("self")` on `TaskDefinitionVersion.child_tasks`.

#### MAP semantics

`type: map` requires exactly two children:

1. **Producer** (child[0]) — executed asynchronously. Its result must be a list.
2. **Consumer** (child[1]) — the task to apply to each element.

Runtime flow:
- The producer is dispatched via `apply_async()`; the MAP task's arguments are forwarded as its kwargs.
- A built-in `map` bound task (registered in `scripts/core/`) receives the producer's resolved result as `items` and the consumer's `TaskInstance` pk as `target_pk`.
- The `map` function iterates the items list and calls `consumer.delay(item)` for each element.
- All consumer calls run in parallel via the normal task dispatch pipeline.
- The MAP task enters `WAITING_RESULTTASKS` until every consumer call completes.

### SCRIPT semantics

`type: script` (or just the `script:` key) declares an arbitrary executable. The value of the `script` field is the relative path to the executable file.

```yaml
- name: deploy
  script: deploy.sh
  description: Deploy the application
```

Runtime flow:
- The file is located in the versioned runtime folder.
- Positional arguments are passed as CLI arguments to the executable.
- Keyword arguments are serialised as JSON on stdin.
- On success, stdout is returned (parsed as JSON if valid, otherwise as plain text).
- On non-zero exit, a ``RuntimeError`` is raised with stderr.
- If ``bound: True``, the environment variable ``AGENTONE_SESSION_ID`` is set.

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
# pipe_names: []                   # (removed — use DataCollection streams/sets instead)
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

## `stream.md` / `set.md` — Data Flow Definition

Defines a data flow (stream or set) that collects and processes task results. Lives at `.agentone/streams/<name>.md` or `.agentone/sets/<name>.md`.

The directory determines the type: `streams/` → append-only stream (auto member/score), `sets/` → mutable ordered set (user-defined member/score).

### YAML Frontmatter Fields

| Field | Required | Type | Default | Description |
|---|---|---|---|---|
| `name` | yes | string | — | Collection name (unique) |
| `description` | no | string | `""` | Human-readable description |
| `sources` | yes | list | `[]` | Source definitions (see below) |
| `processor` | yes | dict | `{}` | Agent + function that transforms items |
| `processor.agent` | yes | string | — | Agent name for the processor task |
| `processor.function` | yes | string | — | Task function name |
| `processor.session` | no | string | `"default"` | Session name (supports `{source_agent.name}` template) |
| `on_removed` | no | dict | `{}` | Handler fired when a set item is removed |
| `on_removed.agent` | yes | string | — | Agent for the removal handler |
| `on_removed.function` | yes | string | — | Task function for the removal handler |
| `member_field` | no | string | `""` | Python eval expression for set member (sets only) |
| `score_field` | no | string | `""` | Python eval expression for set score (sets only) |
| `retroactive_on_source_change` | no | int | `0` | Max items to reprocess when sources change (0=off) |
| `max_reprocess` | no | int | `0` | Max items to reprocess on processor update (0=off) |

### Source definitions

Each entry in `sources` has a `type` field:

| Type | Extra fields | Behaviour |
|---|---|---|
| `query` | `project`, `agent`, `session`, `function` (all string/glob/list) | Match completed `AgentTaskCall` records |
| `stream` | `stream: "<name>"` | Source from another stream's items |
| `set` | `set: "<name>"` | Source from another set's items |

### Example: Stream (append-only)

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
    access:                       # optional — base filesystem access rules
      read:
        default: allow
        deny: ["**/*.env", "secrets/**"]
      write:
        default: allow
        ask: ["scratch/**"]
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
| `access` | no | dict | Base filesystem access policy (see [Access Policy](#access-policy)) |

The `access:` block follows the same shape as the agent `access:` block but
applies *inside* the workspace only — its patterns must be workspace-relative
(no leading `/`, no `..`, no `~`). Agents inherit these rules as the base for
their in-workspace behavior, and may tighten them via their own `workspace:`
override. Leaving `access` unset allows unrestricted access inside the
workspace.

```yaml
access:
  read:
    default: allow              # allow | ask | deny
    allow: []
    ask: []
    deny: ["**/*.env", "secrets/**"]
  write:
    default: deny               # read-only workspace == write.default: deny
    allow: ["inbox/**"]
    ask: ["scratch/**"]
    deny: []
```

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
2. Manifests use `---` both to open **and** close the frontmatter block
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

---

## Upstream Sources (``sources.yaml``)

AgentOne can merge agents, scripts, and skills from remote git repositories. Each source file lives in the relevant subdirectory:

| File | Purpose |
|---|---|
| ``.agentone/skills/skills.yaml`` | Upstream skill repos |
| ``.agentone/agents/sources.yaml`` | Upstream agent repos |
| ``.agentone/scripts/sources.yaml`` | Upstream script/tool repos |

### Format

```yaml
sources:
  - repo: https://github.com/agentone/official-skills.git
    ref: main
  - repo: https://github.com/community/extra-tools.git
    ref: v2.1
    include:           # optional — sync only these paths
      - filesystem/*
      - git/*
```

### How it works during reload

1. **Collect** — ``sync_upstream_sources()`` reads all three source YAML files
2. **Clone/Fetch** — each upstream repo is cloned into ``~/.agentone/upstream/<name>-<hash>/`` (or fetched if already present), then checked out to the configured ``ref``
3. **Merge** — a staging directory is built:
   - Upstream content is copied in first (from each repo's ``.agentone/`` subdirectory — or the repo root if no ``.agentone/`` exists)
   - Local ``.agentone/`` files are copied on top — **local always wins** on path conflicts
4. **Sync** — the staging directory replaces the local ``.agentone/`` as the install repo's source root; ``rsync`` + ``git commit`` proceed normally
5. **Version detection** — upstream files produce git tree SHAs identical to local files; ``get_or_create`` works the same way

### Notes

- Source YAML files with empty ``sources:`` lists (or no ``sources`` key at all) are silently skipped
- If no sources are configured across all three files, the reload process is identical to the pre-upstream behavior
- Local source YAML files themselves (``skills.yaml``, ``sources.yaml``) are **not** copied into the staging directory — they are configuration only, not manifest content

---

**See also:** [Architecture](architecture.md) · [Core mechanisms](core-mechanisms.md) · [Models](models.md) · [Skills format](skills.yaml.md)
