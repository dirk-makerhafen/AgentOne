---
name: baseagent
model: gemma4:26b
description: Core functions available for all.
extends: []
maxRetries: 0
maxTurns: 1
reasoningEffort: medium
maxUnattendedTurns: 1
maxHistoryMessages: 1
schedulerStrategy: queue
subagentResultDelivery: immediate
toolCallSyntax: default
skills: []
disallowedSkills: []
tools: [append, copy, edit, glob, grep, mkdir, move, multiedit, python, read, rm, shell, stat, write]
disallowedTools: []
tasks: [ ingest_user_message, process_turn, build_llm_context, call_llm, parse_llm_response, ingest_assistant_message, decide_next_step, ingest_slash_command, process_slashcommand, handle_slashcommand_response  ]
disallowedTasks: []
commands: [ ping ]
disallowedCommands: []
priority: 0
---

basic agent 
