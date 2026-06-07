---
group: loop_agent
tasks:
  - name: append_processed
    file: append_processed.py
    function: append_processed
  - name: filter_zero
    file: filter_zero.py
    function: filter_zero
  - name: filter_one
    file: filter_one.py
    function: filter_one
  - name: cleanup
    file: cleanup.py
    function: cleanup
---
