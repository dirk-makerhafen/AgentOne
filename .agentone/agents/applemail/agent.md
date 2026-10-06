---
name: applemail
# No tools key -> inherits AgentOne's; exclude the browser explicitly
# (see docs/browser.md).
disallowedTools: [browser.*]
inheritSystemPrompt: true
description: Sync applemail to filesystem
tasks: [core.*]
commands: [ sync_applemail ]
---
