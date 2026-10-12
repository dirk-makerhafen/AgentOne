---
group: workitem
tools:
  # Show one work item in full, with children
  - name: describe_workitem
    file: workitem.py
    function: describe_workitem
    bound: True

  # Update one work item, or move it to a new status
  - name: update_workitem
    file: workitem.py
    function: update_workitem
    bound: True

  # Break one work item into a subtask
  - name: add_child_workitem
    file: workitem.py
    function: add_child_workitem
    bound: True
---
