---
name: health_check
description: Run system health check every 5 minutes
schedule: "*/5 * * * *"
agent: collector
function_type: task
function_name: health_check
session_mode: new
is_active: true
message: {"task": "run"}
---
