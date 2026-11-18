---
name: workitem-admin
description: Admin skill for work item management. Provides commands to list, create, update, split, and move work items through their lifecycle with verification support.
---

# Workitem Admin Skill

This skill documents the admin tools for work item management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_workitem_list
List work items in the current scope with pagination.

**Parameters:**
- `status` (optional): Filter by status (backlog, ready, in_progress, in_review, done, blocked, cancelled)
- `offset` (optional, default: 0): Pagination offset
- `limit` (optional, default: 50): Max items to return

### admin_workitem_stats
Get work item queue statistics (total, by status, blocked count, verification exhausted count).

### admin_workitem_details
Get detailed information about a work item including parent, children, and assigned agent.

**Parameters:**
- `work_item_id` (required): Work item primary key

### admin_workitem_create
Create a new work item (dispatched verbatim to executor agent).

**Parameters:**
- `title` (required): Work item title
- `body` (required): Full requirement/description
- `assigned_agent` (required): Agent name to dispatch to
- `requires_verification` (optional, default: false): Whether reviewer must approve
- `parent_id` (optional): Parent work item for hierarchical tasks

### admin_workitem_update
Update a work item's fields or move it through its lifecycle.

**Parameters:**
- `work_item_id` (required): Work item primary key
- `title` (optional): New title
- `body` (optional): New body
- `status` (optional): New status - see legal transitions below
- `assigned_agent` (optional): New assigned agent
- `requires_verification` (optional): Toggle verification
- `blocked_reason` (optional): Required when moving to 'blocked'

**Legal Status Transitions:**
- `backlog` → `ready`, `blocked`, `cancelled`
- `ready` → `backlog`, `blocked`, `cancelled`
- `in_progress` → `done*`, `blocked`, `cancelled` (*refused while verification pending)
- `in_review` → `done`, `backlog`, `blocked`, `cancelled`
- `blocked` → `ready`, `backlog`, `cancelled`
- `cancelled` → `ready`, `backlog`
- `done` is terminal

### admin_workitem_split
Split a work item into a child task (create_child_workitem).

**Parameters:**
- `work_item_id` (required): Parent work item ID
- `title` (required): Child title
- `body` (required): Child requirement
- `assigned_agent` (required): Child's assigned agent
- `requires_verification` (optional): Whether child requires verification

### admin_workitem_block
Block a work item with a reason (convenience wrapper).

**Parameters:**
- `work_item_id` (required): Work item primary key
- `reason` (required): Block reason

### admin_workitem_unblock
Unblock a work item (move to ready or backlog).

**Parameters:**
- `work_item_id` (required): Work item primary key
- `status` (optional, default: "ready"): Status to move to (ready or backlog)

## Usage Examples

```
# List work items
admin_workitem_list()
admin_workitem_list(status="ready")
admin_workitem_list(status="in_progress", limit=20)

# Create a work item
admin_workitem_create(
    title="Fix login bug",
    body="Users cannot login with OAuth. Debug and fix the callback handler.",
    assigned_agent="coding",
    requires_verification=true
)

# Move through lifecycle
admin_workitem_update(work_item_id=1, status="ready")
admin_workitem_update(work_item_id=1, status="in_progress")
admin_workitem_update(work_item_id=1, status="in_review")
admin_workitem_update(work_item_id=1, status="done")

# Block/unblock
admin_workitem_block(work_item_id=1, reason="Waiting for API key")
admin_workitem_unblock(work_item_id=1, status="ready")

# Split into child
admin_workitem_split(
    work_item_id=1,
    title="Update tests",
    body="Add unit tests for the OAuth callback fix",
    assigned_agent="coding"
)
```

## Verification Workflow

When `requires_verification=true`:
1. Executor completes work → moves to `in_review`
2. Reviewer inspects → approves → moves to `done`
3. Reviewer rejects → moves back to `in_progress` with feedback
4. Max 3 verification attempts by default (configurable)

## Scope Behavior

- **Project-scoped session**: Shows that project's work items
- **Global session**: Shows global inbox work items
- Parent-child hierarchy respected within scope