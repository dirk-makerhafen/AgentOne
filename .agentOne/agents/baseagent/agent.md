---
name: baseagent
model: Qwen3.6-35B-A3B-UD-MLX-4bit
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 200
maxUnattendedTurns: 200
maxHistoryMessages: 1000
autoCompactLimit: 120000
compactSizeLimit: 15
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
commands: [ ping, debug, test-approval, compact, tasks.* ]
disallowedCommands: []
priority: 0
---

basic agent 
