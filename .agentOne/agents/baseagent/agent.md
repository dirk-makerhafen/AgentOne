---
name: baseagent
model: Qwen3.6-35B-A3B-4bit
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 2
maxUnattendedTurns: 0
maxHistoryMessages: 0
reasoningEffort: medium
schedulerStrategy: queue
precision: balanced
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: []
disallowedTools: []
tasks: [ core.*  ]
disallowedTasks: []
commands: [ ping, debug, test-approval ]
disallowedCommands: []
priority: 0
---

basic agent 
