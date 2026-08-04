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
inheritSystemPrompt: false
skills: []
disallowedSkills: []
tools: []
disallowedTools: []
tasks: [ core.*, compact.*  ]
disallowedTasks: []
commands: [ ping, debug, test-approval, tasks.* ]
disallowedCommands: []
priority: 0
---


## Completing Tasks

When you have finished your work, you MUST call the `final_result` tool to return your answer and end the turn.

- **Do not** end with a text-only message — the system will not stop without `final_result`.
- If you are a **subtask** (spawned by another agent), use `final_result` to return your result to the parent.
- If you are in a **chat** (user conversation), use `final_result` to complete your response after using tools.

Example: `final_result(content="Done. I created the file src/app.py with the implementation.")`
