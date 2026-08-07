---
group: core
tasks:
  - name: ingest_user_message
    file: ingest_user_message.py
    function: ingest_user_message
    bound: True
  - name: build_llm_context
    file: build_llm_context.py
    function: build_llm_context
    bound: True
    max_retries: 3    
    retry_delay: 60
  - name: call_llm
    file: call_llm.py
    function: call_llm
    bound: True
    max_retries: 3    
    retry_delay: 60
  - name: parse_llm_response
    file: parse_llm_response.py
    function: parse_llm_response
    bound: True
  - name: ingest_assistant_message
    file: ingest_assistant_message.py
    function: ingest_assistant_message
    bound: True
    max_retries: 3    
    retry_delay: 60
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
  - name: map
    file: map.py
    function: map
    bound: True
  - name: compact_if_needed
    file: compact_if_needed.py
    function: compact_if_needed
    bound: True
  - name: process_turn
    type: chain
    chain:
      - build_llm_context
      - call_llm
      - parse_llm_response
      - ingest_assistant_message
      - compact_if_needed
      - decide_next_step
  - name: ingest_slash_command
    type: chain
    chain:
      - process_slashcommand
      - handle_slashcommand_response

  # Have the subagent return a result to the caller
  - name: final_result
    file: final_result.py
    function: final_result
    bound: True
    
  - name: catch_tool_argument_error
    file: catch_tool_argument_error.py
    function: catch_tool_argument_error
    bound: True
---
some desc