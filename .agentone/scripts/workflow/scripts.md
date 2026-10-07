---
group: workflow
tools:
  - name: workflow_create
    file: workflow.py
    function: workflow_create
    bound: True
    access: write
  - name: workflow_update
    file: workflow.py
    function: workflow_update
    bound: True
    access: write
  - name: workflow_list
    file: workflow.py
    function: workflow_list
    bound: True
    access: read
  - name: workflow_get
    file: workflow.py
    function: workflow_get
    bound: True
    access: read
  - name: workflow_delete
    file: workflow.py
    function: workflow_delete
    bound: True
    access: write
  - name: workflow_validate
    file: workflow.py
    function: workflow_validate
    bound: True
    access: read
  - name: workflow_run
    file: workflow.py
    function: workflow_run
    bound: True
    access: write
tasks:
  # Internal — one link of a workflow's non-blocking execution chain
  - name: workflow_step
    file: workflow_tasks.py
    function: workflow_step
    bound: True
  # Internal — continues after a tool step's call ends
  - name: workflow_advance
    file: workflow_tasks.py
    function: workflow_advance
    bound: True
  # Internal — continues after a group's branches all end
  - name: workflow_join
    file: workflow_tasks.py
    function: workflow_join
    bound: True
  # Internal — continues after a map's producer ends (dispatches wave 1)
  - name: workflow_fanout
    file: workflow_tasks.py
    function: workflow_fanout
    bound: True
  # Internal — continues after a map wave ends (next wave or next step)
  - name: workflow_mapjoin
    file: workflow_tasks.py
    function: workflow_mapjoin
    bound: True
  # Internal — runs one inline function step body (dispatched like a tool leaf)
  - name: workflow_inline
    file: workflow_tasks.py
    function: workflow_inline
    bound: True
---
Session-private dynamic workflows. Workflows are ordered tool-call recipes
that live only for this session (versioned rows, gone with the session
links) and are NEVER registered globally — `workflow_run` is the only way
to run them. There is no promotion path in V1.
