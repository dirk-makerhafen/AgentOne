---
name: baseagent
model: gemma4:26b
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 2
reasoningEffort: medium
maxUnattendedTurns: 2
maxHistoryMessages: 1
schedulerStrategy: queue
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: [filesystem-read.* , filesystem-write.*, subagents.*, web.*, execution.*]
disallowedTools: []
tasks: [ core.*  ]
disallowedTasks: []
commands: [ ping ]
disallowedCommands: []
priority: 0
---

basic agent 
