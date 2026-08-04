---
name: applemail
extends: baseagent
inheritSystemPrompt: true
description: Sync applemail to filesystem
tasks: [ +, email_received, sync ]
commands: [ +, sync_applemail ]
---
