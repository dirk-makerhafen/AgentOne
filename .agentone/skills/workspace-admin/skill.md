---
name: workspace-admin
description: Admin skill for workspace management. Provides commands to list, create, edit, and inspect workspaces, plus create chat sessions.
---

# Workspace Admin Skill

This skill documents the admin tools for workspace management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_workspace_list
List all workspaces in the current scope.

**Parameters:**
- `include_nested` (optional, default: true): Include sub-workspaces

### admin_workspace_stats
Get workspace collection statistics (total, top-level, nested counts).

### admin_workspace_details
Get detailed information about a workspace including sub-workspaces, active sessions, and scoped resources (skills, agents, cronjobs).

**Parameters:**
- `workspace_pk` (optional): Defaults to current session's workspace.

### admin_workspace_create
Create a new workspace at a filesystem path.

**Parameters:**
- `name` (required): Workspace name
- `path` (required): Existing directory path
- `description` (optional): Workspace description
- `parent_workspace_pk` (optional): Parent workspace for nesting

### admin_workspace_rename
Rename a workspace.

**Parameters:**
- `workspace_pk` (required): Workspace primary key
- `name` (required): New name

### admin_workspace_edit
Update a workspace's description.

**Parameters:**
- `workspace_pk` (required): Workspace primary key
- `description` (optional): New description

### admin_workspace_create_chat
Create a new chat session in a workspace.

**Parameters:**
- `workspace_pk` (optional): Defaults to current session's workspace
- `agent_name` (optional, default: "general-chat"): Agent to use
- `title` (optional): Session title

### admin_workspace_dashboard
Get or update a workspace's markdown dashboard.

**Parameters:**
- `workspace_pk` (optional): Defaults to current session's workspace
- `content` (optional): If provided, writes content. If omitted, reads current.

## Usage Examples

```
# List workspaces
admin_workspace_list()

# Create a workspace
admin_workspace_create(name="frontend", path="/home/user/frontend", description="Frontend work")

# Create nested workspace
admin_workspace_create(name="api", path="/home/user/frontend/api", parent_workspace_pk=1)

# Create a chat session
admin_workspace_create_chat(agent_name="coding", title="Fix auth bug")

# View/edit dashboard
admin_workspace_dashboard()
admin_workspace_dashboard(content="# Frontend Workspace\n\nActive tasks...")
```

## Scope Behavior

- **Project-scoped session**: Shows workspaces owned by that project
- **Global session**: Shows global workspaces
- Path nesting (`parent_workspace`) and ownership (`parent_project`) are orthogonal
- Workspace path must be inside parent workspace path when nesting