---
group: workitem
tools:
  # Show one work item in full, with children
  - name: workitem_details
    file: workitem.py
    function: workitem_details
    bound: True

  # Update one work item, or move it to a new status
  - name: edit_workitem
    file: workitem.py
    function: edit_workitem
    bound: True

  # Break one work item into a subtask
  - name: create_child_workitem
    file: workitem.py
    function: create_child_workitem
    bound: True
---
