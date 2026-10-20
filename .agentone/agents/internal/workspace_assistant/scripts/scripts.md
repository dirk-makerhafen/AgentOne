---
group: workspace
tools:
  # Key details of the managed workspace in one call (totals, counts)
  - name: workspace_details
    file: workspace.py
    function: workspace_details
    bound: True

  # List direct sub-workspaces of the managed workspace
  - name: list_subworkspaces
    file: workspace.py
    function: list_subworkspaces
    bound: True

  # Create a new sub-workspace inside the managed workspace
  - name: create_subworkspace
    file: workspace.py
    function: create_subworkspace
    bound: True

  # Edit description, color or path of the managed (sub-)workspace
  - name: edit_workspace
    file: workspace.py
    function: edit_workspace
    bound: True

  # Rename the managed workspace or one of its sub-workspaces
  - name: rename_workspace
    file: workspace.py
    function: rename_workspace
    bound: True

  # List chat sessions bound to the managed workspace
  - name: list_sessions
    file: workspace.py
    function: list_sessions
    bound: True

  # Create a new normal chat session in the managed workspace
  - name: create_chat
    file: workspace.py
    function: create_chat
    bound: True

  # List skills in the managed workspace's scope
  - name: list_skills
    file: workspace.py
    function: list_skills
    bound: True

  # List agents in the managed workspace's scope
  - name: list_agents
    file: workspace.py
    function: list_agents
    bound: True

  # List cron jobs in the managed workspace's scope
  - name: list_cronjobs
    file: workspace.py
    function: list_cronjobs
    bound: True

  # Reload ONE workspace's scoped manifest tree from disk
  - name: refresh_from_disk
    file: workspace.py
    function: refresh_from_disk
    bound: True
---
