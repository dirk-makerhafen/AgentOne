---
group: subagents
tools:
  # Create or reuse a named background subsession
  - name: start_subsession
    file: start_subsession.py
    function: start_subsession
    bound: True

  # Stop/mark a subsession as inactive
  - name: stop_subsession
    file: stop_subsession.py
    function: stop_subsession
    bound: True

  # Send a message to a named subsession (blocking or async delivery)
  - name: message_subsession
    file: message_subsession.py
    function: message_subsession
    bound: True

  # Block until the subsession's latest message is answered
  - name: await_subsession
    file: await_subsession.py
    function: await_subsession
    bound: True

  # List all subsessions owned by the current session
  - name: list_subsessions
    file: list_subsessions.py
    function: list_subsessions
    bound: True

  # Fork yourself as a child session to do a one-off task
  - name: spawn_subtask
    file: spawn_subtask.py
    function: spawn_subtask
    bound: True

  # Delegate a one-off task to a named agent (new or existing session)
  - name: delegate_task
    file: delegate_task.py
    function: delegate_task
    bound: True

  # List agents available for delegation
  - name: get_available_agents
    file: get_available_agents.py
    function: get_available_agents
    bound: True

  # Have the subagent return a result to the caller
  - name: final_result
    file: final_result.py
    function: final_result
    bound: True
tasks:
  # Internal — delivers subagent result in "immediate" mode
  - name: ingest_subagent_result
    file: ingest_subagent_result.py
    function: ingest_subagent_result
    bound: True
---
