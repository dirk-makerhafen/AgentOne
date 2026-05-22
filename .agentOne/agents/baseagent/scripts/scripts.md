---
tasks:
  - name: ingest_user_message
    file: ingest_user_message.py
    function: ingest_user_message
    bound: True
  - name: build_llm_context
    file: build_llm_context.py
    function: build_llm_context
    bound: True
  - name: call_llm
    file: call_llm.py
    function: call_llm
    bound: True
  - name: parse_llm_response
    file: parse_llm_response.py
    function: parse_llm_response
    bound: True
  - name: ingest_assistant_message
    file: ingest_assistant_message.py
    function: ingest_assistant_message
    bound: True
  - name: decide_next_step  
    file: decide_next_step.py
    function: decide_next_step
    bound: True
  - name: process_slashcommand  
    file: slash_commands.py
    function: process_slashcommand
    bound: True
  - name: handle_slashcommand_response  
    file: slash_commands.py
    function: handle_slashcommand_response
    bound: True
  - name: process_turn
    type: chain
    chain:
      - build_llm_context
      - call_llm
      - parse_llm_response
      - ingest_assistant_message
      - decide_next_step
  - name: ingest_slash_command
    type: chain
    chain:
      - process_slashcommand
      - handle_slashcommand_response

commands:
  - name: ping
    file: ping.py
    function: ping
    bound: True
