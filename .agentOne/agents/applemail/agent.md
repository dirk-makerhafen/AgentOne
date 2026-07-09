---
name: applemail
extends: baseagent
description: Sync applemail to filesystem
tasks: [ +, email_received, sync ]
commands: [ +, sync_applemail ]
---
