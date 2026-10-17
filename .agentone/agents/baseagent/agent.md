---
name: baseagent
visibility: internal
model: Qwen3.6-35B-A3B-UD-MLX-4bit
description: Basic Agent without any tools
extends: []
inheritSystemPrompt: false
maxRetries: 0
maxTurns: 3
maxUnattendedTurns: 20
maxHistoryMessages: 200
autoCompactMaxTokens: 100000
autoCompactKeepPercent: 10
reasoningEffort: high
schedulerStrategy: queue
precision: precise
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: [filesystem-read.*, filesystem-write.*,]
disallowedTools: []
tasks: [core.*]
disallowedTasks: []
commands: []
disallowedCommands: []
priority: 0
---
