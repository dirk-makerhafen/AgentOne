---
name: disallowed_cmds
description: >
  Tests disallowedCommandNames and disallowedTaskNames — pong blocked from
  commands, core.* wildcard blocks core_task. Used by RuntimeAgentTest,
  RuntimeSessionTest.
tools: [fs.*]
commands: [ping, pong]
tasks: [core.*]
disallowedCommands: [pong]
disallowedTasks: [core.*]
---
Agent with disallowed commands and tasks
