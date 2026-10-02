---
group: workspace
tools:
  # List direct sub-workspaces of the managed workspace
  - name: list_subworkspaces
    file: workspaces.py
    function: list_subworkspaces
    bound: True

  # Create a new sub-workspace inside the managed workspace
  - name: create_subworkspace
    file: workspaces.py
    function: create_subworkspace
    bound: True

  # Edit description, color or path of the managed (sub-)workspace
  - name: edit_workspace
    file: workspaces.py
    function: edit_workspace
    bound: True

  # Rename the managed workspace or one of its sub-workspaces
  - name: rename_workspace
    file: workspaces.py
    function: rename_workspace
    bound: True

  # List chat sessions bound to the managed workspace
  - name: list_sessions
    file: workspaces.py
    function: list_sessions
    bound: True

  # Create a new normal chat session in the managed workspace
  - name: create_chat
    file: workspaces.py
    function: create_chat
    bound: True
---
