---
name: chatagent
description: Core chat agent
model: gemma4:26b
extends: baseagent
tasks: add_chat_message, handle_chat_message, handle_user_command, handle_command_response, create_query, decide_next_step
---