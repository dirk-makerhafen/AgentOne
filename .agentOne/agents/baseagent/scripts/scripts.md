---
tasks:
  - name: ingest_user_message
    type: python
    file: ingest_user_message.py
    function: ingest_user_message
    bound: True
  - name: build_llm_context
    type: python
    file: build_llm_context.py
    function: build_llm_context
    bound: True
  - name: call_llm
    type: python
    file: call_llm.py
    function: call_llm
    bound: True
  - name: extract_tool_calls
    type: python
    file: extract_tool_calls.py
    function: extract_tool_calls
    bound: True
  - name: execute_tools
    type: python
    file: execute_tools.py
    function: execute_tools
    bound: True
  - name: decide_next_step  
    type: python
    file: decide_next_step.py
    function: decide_next_step
    bound: True
  - name: process_turn
    type: chain
    chain:
      - build_llm_context
      - call_llm
      - extract_tool_calls
      - execute_tools
      - decide_next_step

commands:
  - name: ping
    type: python
    file: ping.py
    function: ping
    bound: True
    trigger: ping
