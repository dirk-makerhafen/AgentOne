---
name: cronjob-admin
description: Admin skill for cron job management. Provides commands to list, create, edit, pause/resume, archive, and inspect cron jobs and their run history.
---

# Cronjob Admin Skill

This skill documents the admin tools for cron job management available to AgentOne.

## Tools Available

All tools are accessed via the `admin` tool group and are scoped to the current session's project (or global if no project).

### admin_cronjob_list
List all cron jobs in the current scope.

**Parameters:**
- `include_archived` (optional, default: false): Include archived jobs

### admin_cronjob_stats
Get cron job collection statistics (total, active, paused, archived, total runs, next scheduled run).

### admin_cronjob_details
Get detailed information about a cron job including recent run history and target agent info.

**Parameters:**
- `job_pk` (optional): Cron job primary key
- `job_name` (optional): Cron job name (one required)

### admin_cronjob_create
Create a new cron job.

**Parameters:**
- `name` (required): Job name (unique in scope)
- `schedule` (required): Cron schedule - standard (0 9 * * *), shorthands (@daily, @hourly, @weekly, @monthly), or "every N min|hour" (every 30m)
- `agent_name` (required): Target agent to execute
- `session_mode` (optional, default: "normal"): "normal" | "subtask" | "fork"
- `function_type` (optional): Function to call (e.g., "agent_task")
- `message` (optional): Message/args (JSON string if function_type set)

### admin_cronjob_edit
Edit a cron job's configuration.

**Parameters:**
- `job_pk` or `job_name` (required): Target job
- `schedule` (optional): New schedule
- `agent_name` (optional): New agent
- `session_mode` (optional): "normal" | "subtask" | "fork"
- `function_type` (optional): Function type
- `message` (optional): Message/args

### admin_cronjob_pause
Pause a cron job (set is_active=false).

**Parameters:**
- `job_pk` or `job_name` (required): Target job

### admin_cronjob_resume
Resume a cron job (set is_active=true).

**Parameters:**
- `job_pk` or `job_name` (required): Target job

### admin_cronjob_archive
Archive or restore a cron job (archiving implies pausing).

**Parameters:**
- `job_pk` or `job_name` (required): Target job
- `archive` (optional, default: true): True to archive, false to restore

### admin_cronjob_runs
Get run history for a cron job.

**Parameters:**
- `job_pk` or `job_name` (required): Target job
- `limit` (optional, default: 50): Max runs to return

## Usage Examples

```
# List cron jobs
admin_cronjob_list()
admin_cronjob_list(include_archived=true)

# Create a daily job
admin_cronjob_create(
    name="daily-sync",
    schedule="@daily",
    agent_name="coding",
    message='{"task": "Sync dependencies"}'
)

# Create every 30 minutes
admin_cronjob_create(
    name="health-check",
    schedule="every 30m",
    agent_name="general-chat",
    message="Run health check"
)

# Pause/resume
admin_cronjob_pause(job_name="daily-sync")
admin_cronjob_resume(job_name="daily-sync")

# View run history
admin_cronjob_runs(job_name="daily-sync", limit=20)
```

## Schedule Formats

- **Standard cron**: `0 9 * * *` (daily at 9 AM)
- **Shorthands**: `@daily`, `@hourly`, `@weekly`, `@monthly`, `@yearly`
- **Every N**: `every 5m`, `every 30m`, `every 1h`, `every 2h`

## Scope Behavior

- **Project-scoped session**: Shows that project's cron jobs
- **Global session**: Shows global cron jobs
- Jobs target agents by name (must exist)