---
name: disallowed_cmds
tools: [fs.*]
commands: [ping, pong]
tasks: [core.*]
disallowedCommands: [pong]
disallowedTasks: [core.*]
---
Agent with disallowed commands and tasks
