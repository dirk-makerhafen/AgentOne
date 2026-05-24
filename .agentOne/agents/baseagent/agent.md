---
name: baseagent
model: gemma4:26b
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 2
maxUnattendedTurns: 0
maxHistoryMessages: 0
reasoningEffort: medium
schedulerStrategy: queue
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: []
disallowedTools: []
tasks: [ core.*  ]
disallowedTasks: []
commands: [ ping ]
disallowedCommands: []
priority: 0
---

basic agent 
