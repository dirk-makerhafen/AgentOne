---
group: subagents
tools:
  # Sync — blocks until subagent finishes
  - name: delegate_task
    file: delegate_task.py
    function: delegate_task
    bound: True

  # Async — fire-and-forget, returns session_pk
  - name: spawn_subagent
    file: spawn_subagent.py
    function: spawn_subagent
    bound: True

  # Async follow-up — send message to running subagent
  - name: message_subagent
    file: message_subagent.py
    function: message_subagent
    bound: True

  # Sync barrier — wait for one or more spawned subagents to complete
  - name: await_subagents
    file: await_subagents.py
    function: await_subagents
    bound: True

  # Sync instant — list child sessions with metadata (no output)
  - name: list_subagents
    file: list_subagents.py
    function: list_subagents
    bound: True

  # Sync instant — stop/cancel a child session
  - name: stop_subagent
    file: stop_subagent.py
    function: stop_subagent
    bound: True

tasks:
  # Internal — delivers subagent result in "immediate" mode
  - name: ingest_subagent_result
    file: ingest_subagent_result.py
    function: ingest_subagent_result
    bound: True
---
