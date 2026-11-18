---
name: system-admin
description: System admin skill aggregating all admin capabilities. Provides overview commands and references to domain-specific admin skills.
---

# System Admin Skill

This skill aggregates all admin capabilities into a single reference. It documents the complete admin toolset available to AgentOne.

## Domain-Specific Admin Skills

Each domain has its own skill with detailed documentation:

- **project-admin** - Project management (list, create, reload, dashboard)
- **workspace-admin** - Workspace management (list, create, nest, chat sessions)
- **agent-admin** - Agent management (list, create, edit, usage, versions)
- **skill-admin** - Skill management (list, create, assign/unassign, usage)
- **cronjob-admin** - Cron job management (list, create, edit, pause, runs)
- **workitem-admin** - Work item management (list, create, lifecycle, verification)

## Quick Reference: All Admin Tools

### Project Tools
| Tool | Description |
|------|-------------|
| `admin_project_list` | List projects in scope |
| `admin_project_stats` | Cross-project statistics |
| `admin_project_details` | Project details + resources |
| `admin_project_create` | Create new project |
| `admin_project_reload` | Reload manifests from disk |
| `admin_project_dashboard` | Get/set project dashboard |

### Workspace Tools
| Tool | Description |
|------|-------------|
| `admin_workspace_list` | List workspaces |
| `admin_workspace_stats` | Workspace statistics |
| `admin_workspace_details` | Workspace details + sessions |
| `admin_workspace_create` | Create workspace |
| `admin_workspace_rename` | Rename workspace |
| `admin_workspace_edit` | Edit description |
| `admin_workspace_create_chat` | Create chat session |
| `admin_workspace_dashboard` | Get/set workspace dashboard |

### Agent Tools
| Tool | Description |
|------|-------------|
| `admin_agent_list` | List agents (filter by visibility/kind) |
| `admin_agent_stats` | Agent statistics |
| `admin_agent_details` | Agent details + usage + versions |
| `admin_agent_create` | Create agent manifest |
| `admin_agent_edit_manifest` | Edit agent.md live |
| `admin_agent_usage` | Usage stats (sessions, cron, workitems) |
| `admin_agent_versions` | Version history |
| `admin_agent_list_children` | Subagents, skills, cronjobs |

### Skill Tools
| Tool | Description |
|------|-------------|
| `admin_skill_list` | List skills |
| `admin_skill_details` | Skill details + assignments |
| `admin_skill_create` | Create skill manifest |
| `admin_skill_edit_manifest` | Edit skill.md live |
| `admin_skill_assign` | Assign skill to agent (live) |
| `admin_skill_unassign` | Unassign skill from agent (live) |
| `admin_skill_usage` | Skill usage statistics |
| `admin_skill_for_agent` | Agent's effective skills |
| `admin_skill_list_children` | Child skills, owning agents |

### Cronjob Tools
| Tool | Description |
|------|-------------|
| `admin_cronjob_list` | List cron jobs |
| `admin_cronjob_stats` | Cron statistics |
| `admin_cronjob_details` | Job details + run history |
| `admin_cronjob_create` | Create cron job |
| `admin_cronjob_edit` | Edit job config |
| `admin_cronjob_pause` | Pause job |
| `admin_cronjob_resume` | Resume job |
| `admin_cronjob_archive` | Archive/restore job |
| `admin_cronjob_runs` | Run history |

### Workitem Tools
| Tool | Description |
|------|-------------|
| `admin_workitem_list` | List work items (filter/paginate) |
| `admin_workitem_stats` | Queue statistics |
| `admin_workitem_details` | Work item details + hierarchy |
| `admin_workitem_create` | Create work item |
| `admin_workitem_update` | Update fields / lifecycle |
| `admin_workitem_split` | Create child work item |
| `admin_workitem_block` | Block with reason |
| `admin_workitem_unblock` | Unblock to ready/backlog |

## Scope Behavior (All Tools)

- **Project-scoped session**: Operates within the session's project (includes global resources)
- **Global session**: Operates on global resources only
- Workspace operations respect both project ownership (`parent_project`) and path nesting (`parent_workspace`)
- All tools read `_session.workspace` → `session.get_project()` implicitly - no path arguments needed

## Usage Pattern

```python
# All tools follow the same pattern:
result = admin_<domain>_<action>(params)

# Result format:
# (True, {"status": "success", ...})  on success
# (False, {"status": "error", "message": "..."})  on error
```

## Loading These Skills

Add to your agent's `skills:` list in agent.md:

```yaml
skills:
  - project-admin
  - workspace-admin
  - agent-admin
  - skill-admin
  - cronjob-admin
  - workitem-admin
  - system-admin
```

Then reload the agent: `admin_agent_reload` or `admin_project_reload`.