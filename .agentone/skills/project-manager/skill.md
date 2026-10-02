---
name: project-manager
description: >
  Manage a project's .agentone/ directory: list, create, and update agents,
  cron jobs, scripts, skills, streams, sets, and the project manifest itself.
  Uses filesystem tools (glob, read, write, edit) — no shell access.
---

# Project Management Skill

You manage a project's `.agentone/` directory using your filesystem tools.
You cannot run shell commands. After making changes, report what you did so
the caller can run `reload_all` to sync to the database.

## Project Layout

```
<project-root>/
└── .agentone/
    ├── project.md              # Project declaration
    ├── agents/
    │   └── <name>/
    │       ├── agent.md
    │       └── scripts/
    │           ├── scripts.md
    │           └── *.py
    ├── cronjobs/
    │   └── <name>.md
    ├── scripts/
    │   ├── scripts.md
    │   └── *.py
    ├── skills/
    │   └── <name>/
    │       ├── skill.md
    │       └── scripts/
    ├── streams/
    │   └── <name>.md
    └── sets/
        └── <name>.md
```

Your project root path was given to you at creation. All file paths below are
relative to the project root.

## Tool Guide

| Tool | What it does |
|---|---|
| `glob(pattern)` | Find files matching a pattern |
| `read(path)` | Read file contents (supports offset/limit) |
| `write(path, content)` | Create or overwrite a file |
| `edit(path, old, new)` | Replace text in an existing file |
| `mkdir(path)` | Create directories |
| `append(path, content)` | Add content to end of a file |
| `stat(path)` | File metadata |
| `tree(path)` | Directory tree view |
| `load_skill(name)` | Load a skill file for reference |
| `reload_project(path)` | Sync manifests to DB. Returns summary with counts + any errors |

## Manifest Format Reference

Load the `agentone-admin` skill for the complete YAML schema:

```
load_skill("agentone-admin")
```

## Common Tasks

### List agents

```
glob("**/agent.md")
```

Then `read` each file and extract name, model, description, extends from
the YAML frontmatter.

### List cron jobs

```
glob("cronjobs/*.md")
```

Read each file's YAML frontmatter for name, schedule, agent.

### List scripts/tools

```
glob("scripts/**/scripts.md")
```

Read the tools/tasks/commands sections from each scripts.md.

### List skills

```
glob("skills/*/skill.md")
```

Read the YAML frontmatter for name and description.

### List data flows

```
glob("streams/*.md")
glob("sets/*.md")
```

### Create a new agent

1. `mkdir("agents/<name>/scripts")` — create directories
2. `write("agents/<name>/agent.md", content)` — YAML frontmatter + body
3. If custom scripts needed: `write("agents/<name>/scripts/scripts.md", content)`

### Edit a manifest

1. `read(path)` — current contents
2. `edit(path, old_string, new_string)` — make changes

### Create a cron job

1. `write("cronjobs/<name>.md", content)` — YAML frontmatter with schedule

## After Changes

Always sync by calling `reload_project("<project-root>")` after creating or
editing any manifest files. This updates the database to reflect your
changes.

The tool returns a summary like::

    Loaded: 2 agents, 3 scripts/tools, 1 skill, 1 cron job.

If there were errors, they're listed individually. Report the summary to the
caller so they know what was loaded and whether anything failed.
