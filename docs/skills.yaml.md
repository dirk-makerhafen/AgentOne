# Skills

Skills are capability bundles that add tools, tasks, and commands to agents. They follow the same manifest structure as agents.

## Structure

```
.agentone/skills/<name>/
├── skill.md                 # Skill declaration with YAML frontmatter
└── scripts/
    ├── scripts.md           # Task/tool/command definitions
    └── *.py                 # Python implementations
```

## `skill.md`

```yaml
---
name: document-scanner
description: Scan and OCR documents
---
Optional skill description in markdown.
```

## Loading

Skills are loaded automatically from `.agentone/skills/` by the manifest loader (via `python3 manage.py reload_all` or server startup). You can also install skills from remote repositories — see `install_repo.py` for the git-based install mechanism.

## Assignment to agents

Agents declare which skills they use in their `agent.md`:

```yaml
skills:
  - document-scanner
```

Skills resolved through the agent's version chain are available to that agent's sessions.
