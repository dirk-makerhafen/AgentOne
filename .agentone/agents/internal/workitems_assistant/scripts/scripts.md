---
group: workitems_mgmt
tools:
  # List work items in the managed project scope
  - name: list_workitems
    file: workitems.py
    function: list_workitems
    bound: True

  # Queue health overview: counts by status + items needing attention
  - name: workitems_stats
    file: workitems.py
    function: workitems_stats
    bound: True

  # File a new work item
  - name: create_workitem
    file: workitems.py
    function: create_workitem
    bound: True
---
