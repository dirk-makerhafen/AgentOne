---
name: project-admin
description: Admin skill for project management. Provides commands to list, create, reload, and inspect projects in the current scope.
---

# Project Admin Skill

This skill documents the admin tools for project management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_project_list
List all projects visible in the current scope.

**Parameters:** none

**Returns:** List of projects with name, path, description, and current-project flag.

### admin_project_stats
Get cross-project statistics including agent, skill, cronjob, workspace, and workitem counts per project.

**Parameters:** none

### admin_project_details
Get detailed information about a specific project including its agents, skills, cronjobs, workspaces, and workitems.

**Parameters:**
- `project_pk` (optional): Project primary key. Defaults to current scope's project.

### admin_project_create
Create a new project with optional filesystem path and description.

**Parameters:**
- `name` (required): Globally unique project name
- `path` (optional): Filesystem path for project root
- `description` (optional): Project description
- `manifest_in_workspace` (optional): If path is a workspace, put manifests there

### admin_project_reload
Reload a project's manifests from disk (agents, skills, scripts, cronjobs).

**Parameters:**
- `project_pk` (optional): Defaults to current scope's project.

### admin_project_dashboard
Get or update a project's markdown dashboard.

**Parameters:**
- `project_pk` (optional): Defaults to current scope's project.
- `content` (optional): If provided, writes content to dashboard. If omitted, reads current.

## Usage Examples

```
# List projects
admin_project_list()

# Get stats across projects
admin_project_stats()

# Create a new project
admin_project_create(name="my-project", path="/path/to/project", description="My project")

# Reload current project
admin_project_reload()

# View dashboard
admin_project_dashboard()
admin_project_dashboard(content="# My Project Dashboard\n\nWelcome!")
```

## Scope Behavior

- **Project-scoped session**: Shows the current project + global projects
- **Global session**: Shows only global projects
- All operations respect scope boundaries