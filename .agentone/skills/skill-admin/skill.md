---
name: skill-admin
description: Admin skill for skill management. Provides commands to list, create, edit, and inspect skills, plus assign/unassign skills to agents.
---

# Skill Admin Skill

This skill documents the admin tools for skill management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_skill_list
List all skills visible in the current scope.

**Parameters:** none

### admin_skill_details
Get detailed information about a skill including assigned agents, loading agents, child skills, and owning agents.

**Parameters:**
- `skill_pk` (optional): Skill primary key
- `skill_name` (optional): Skill name (one required)

### admin_skill_create
Create a new skill manifest in the current project scope.

**Parameters:**
- `name` (required): Skill name
- `description` (optional): Description

### admin_skill_edit_manifest
Edit a skill's skill.md manifest directly with live effect.

**Parameters:**
- `skill_pk` (required): Skill primary key
- `changes` (required): Dict of field -> new value

### admin_skill_assign
Assign a skill to an agent (immediate live effect).

**Parameters:**
- `agent_pk` or `agent_name` (required): Target agent
- `skill_pk` or `skill_name` (required): Skill to assign

**Note:** Assignment is live immediately. For permanence, edit agent.md `skills:` list and reload.

### admin_skill_unassign
Unassign a skill from an agent (immediate live effect).

**Parameters:**
- `agent_pk` or `agent_name` (required): Target agent
- `skill_pk` or `skill_name` (required): Skill to unassign

### admin_skill_usage
Get usage statistics for a skill (which agents have it assigned/loaded).

**Parameters:**
- `skill_pk` (optional): Skill primary key
- `skill_name` (optional): Skill name (one required)

### admin_skill_for_agent
Show one agent's effective skills (assigned + inherited).

**Parameters:**
- `agent_pk` (optional): Agent primary key
- `agent_name` (optional): Agent name (one required)

### admin_skill_list_children
List a skill's children: child skills and owning agents.

**Parameters:**
- `skill_pk` (optional): Skill primary key
- `skill_name` (optional): Skill name (one required)

## Usage Examples

```
# List skills
admin_skill_list()

# Create a skill
admin_skill_create(name="my-skill", description="Custom skill for X")

# Assign skill to agent
admin_skill_assign(agent_name="coding", skill_name="project-admin")

# View agent's skills
admin_skill_for_agent(agent_name="coding")

# Unassign
admin_skill_unassign(agent_name="coding", skill_name="project-admin")
```

## Scope Behavior

- **Project-scoped session**: Shows global skills + project's own skills
- **Global session**: Shows only global skills
- Child skills are linked via parent_skill
- Owning agents have the skill as their parent_skill
- Assign/unassign are live; manifest edits persist