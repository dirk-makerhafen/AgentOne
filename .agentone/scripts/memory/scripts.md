---
group: memory
tools:
  - name: memory_collect_inputs
    file: memory_collect_inputs.py
    function: memory_collect_inputs
    bound: True
  - name: memory_process_queue
    file: memory_process_queue.py
    function: memory_process_queue
    bound: True
  - name: memory_collect_results
    file: memory_collect_results.py
    function: memory_collect_results
    bound: True
  - name: memory_walk
    file: memory_walk.py
    function: memory_walk
    bound: False
tasks:
  - name: memory_synthesize_task
    file: memory_synthesize_task.py
    function: memory_synthesize_task
    bound: True
  - name: memory_synthesize_agent
    file: memory_synthesize_agent.py
    function: memory_synthesize_agent
    bound: True
  - name: memory_synthesize_scope
    file: memory_synthesize_scope.py
    function: memory_synthesize_scope
    bound: True
  - name: memory_tick
    type: chain
    chain:
      - memory_collect_inputs
      - memory_process_queue
---

Memory management pipeline (collect inputs, process queue, synthesize).
