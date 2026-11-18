---
name: agent-admin
description: Admin skill for agent management. Provides commands to list, create, edit, and inspect agents, plus view usage and version history.
---

# Agent Admin Skill

This skill documents the admin tools for agent management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_agent_list
List all agents visible in the current scope.

**Parameters:**
- `visibility` (optional): Filter by 'user', 'subagent', 'internal', 'mixin'
- `kind` (optional): Filter by 'root' (top-level) or 'child' (subagent/skill-owned)

### admin_agent_stats
Get agent collection statistics (total, by visibility, by kind).

### admin_agent_details
Get detailed information about an agent including version, usage stats, children, and version history.

**Parameters:**
- `agent_pk` (optional): Agent primary key
- `agent_name` (optional): Agent name (one required)

### admin_agent_create
Create a new agent manifest in the current project scope.

**Parameters:**
- `name` (required): Agent name
- `model` (required): Model name (e.g., "gpt-4o")
- `description` (optional): Description
- `extends` (optional): Parent agent(s) - comma-separated string or array
- `visibility` (optional, default: "user"): 'user', 'subagent', 'internal', 'mixin'
- `tools` (optional): List of tool group names
- `skills` (optional): List of skill names
- `subagents` (optional): List of subagent configs (strings or dicts)

### admin_agent_edit_manifest
Edit an agent's agent.md manifest directly with live effect.

**Parameters:**
- `agent_pk` (required): Agent primary key
- `changes` (required): Dict of field -> new value

### admin_agent_usage
Get usage statistics for an agent (sessions, cronjobs, workitems).

**Parameters:**
- `agent_pk` (optional): Agent primary key
- `agent_name` (optional): Agent name (one required)

### admin_agent_versions
Get version history for an agent.

**Parameters:**
- `agent_pk` (optional): Agent primary key
- `agent_name` (optional): Agent name (one required)

### admin_agent_list_children
List an agent's children: subagents, skills, cronjobs.

**Parameters:**
- `agent_pk` (optional): Agent primary key
- `agent_name` (optional): Agent name (one required)

## Usage Examples

```
# List agents
admin_agent_list()
admin_agent_list(visibility="user")
admin_agent_list(kind="root")

# Create an agent
admin_agent_create(
    name="my-agent",
    model="gpt-4o",
    description="Custom agent",
    extends=["baseagent"],
    tools=["filesystem", "execution"],
    skills=["project-admin"]
)

# Edit manifest
admin_agent_edit_manifest(agent_pk=1, changes={"model": "gpt-4o-mini", "description": "Updated"})

# View usage and versions
admin_agent_usage(agent_name="coding")
admin_agent_versions(agent_name="coding")
```

## Scope Behavior

- **Project-scoped session**: Shows global agents + project's own agents
- **Global session**: Shows only global agents
- Child agents (subagents, skill-owned) are linked via parent_agent/parent_skill
- Manifest edits are live immediately; reload for permanent effect