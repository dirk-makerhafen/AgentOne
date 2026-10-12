---
group: workspaces
tools:
  # List ALL workspaces on the instance
  - name: list_workspaces
    file: workspaces.py
    function: list_workspaces
    bound: True

  # Create a new top-level workspace
  - name: create_workspace
    file: workspaces.py
    function: create_workspace
    bound: True

  # Collection health: total / top-level / nested counts
  - name: workspaces_stats
    file: workspaces.py
    function: workspaces_stats
    bound: True
---
