---
name: baseagent
model: gemma4:26b
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 0
reasoningEffort: high
maxUnattendedTurns: 0
maxHistoryMessages: 0
executionMode: queue
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: [append, copy, edit, glob, grep, mkdir, move, multiedit, python, read, rm, shell, stat, write]
disallowedTools: []
tasks: [ ingest_user_message, process_turn, build_llm_context, call_llm, extract_tool_calls, execute_tools, decide_next_step ]
disallowedTasks: []
commands: [ ping ]
disallowedCommands: []
priority: 0
---

ping
