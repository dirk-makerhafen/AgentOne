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
tasks: [ handle_user_message, handle_assistant_message, process_chat_message, process_task_message, process_message, create_query, execute_query, parse_response, decide_next_step ]
disallowedTasks: []
commands: [ ping ] 
disallowedCommands: []
priority: 0
---

ping
