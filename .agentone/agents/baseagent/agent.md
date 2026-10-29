---
name: baseagent
visibility: internal
model: Qwen3.6-35B-A3B-UD-MLX-4bit
description: Basic Agent with only filesystem read/write
extends: []
inheritSystemPrompt: false
maxRetries: 3
maxTurns: 999
maxUnattendedTurns: 999
maxHistoryMessages: 999
autoCompactMaxTokens: 120000
autoCompactMaxTokens: 25000
autoCompactKeepPercent: 5
autoCompactTimeout: 240
reasoningEffort: high
schedulerStrategy: queue
precision: precise
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: [filesystem-read.*, filesystem-write.*,]
disallowedTools: []
tasks: [core.*, compact.*]
disallowedTasks: []
commands: []
disallowedCommands: []
priority: 99
---
