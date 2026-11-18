---
group: admin
tools:
  - name: list
    file: list.py
    function: list_workspaces
    bound: True
  - name: stats
    file: stats.py
    function: stats
    bound: True
  - name: details
    file: details.py
    function: details
    bound: True
  - name: create
    file: create.py
    function: create
    bound: True
  - name: rename
    file: rename.py
    function: rename
    bound: True
  - name: edit
    file: edit.py
    function: edit
    bound: True
  - name: create_chat
    file: create_chat.py
    function: create_chat
    bound: True
  - name: dashboard
    file: dashboard.py
    function: dashboard
    bound: True
tasks:
  - name: admin_workspace_list
    file: list.py
    function: list_workspaces
    bound: True
    description: List all workspaces in current scope
    parameters:
      - name: include_nested
        type: boolean
        description: Include sub-workspaces
  - name: admin_workspace_stats
    file: stats.py
    function: stats
    bound: True
    description: Get workspace collection statistics
  - name: admin_workspace_details
    file: details.py
    function: details
    bound: True
    description: Get detailed information about a workspace
    parameters:
      - name: workspace_pk
        type: integer
        description: Optional workspace primary key (defaults to current scope)
  - name: admin_workspace_create
    file: create.py
    function: create
    bound: True
    description: Create a new workspace
    parameters:
      - name: name
        type: string
        description: Workspace name (required)
      - name: path
        type: string
        description: Filesystem path (must be an existing directory)
      - name: description
        type: string
        description: Optional description
      - name: parent_workspace_pk
        type: integer
        description: Optional parent workspace for nesting
  - name: admin_workspace_rename
    file: rename.py
    function: rename
    bound: True
    description: Rename a workspace
    parameters:
      - name: workspace_pk
        type: integer
        description: Workspace primary key
      - name: name
        type: string
        description: New name
  - name: admin_workspace_edit
    file: edit.py
    function: edit
    bound: True
    description: Update a workspace's description
    parameters:
      - name: workspace_pk
        type: integer
        description: Workspace primary key
      - name: description
        type: string
        description: New description
  - name: admin_workspace_create_chat
    file: create_chat.py
    function: create_chat
    bound: True
    description: Create a new chat session in a workspace
    parameters:
      - name: workspace_pk
        type: integer
        description: Optional workspace primary key (defaults to current)
      - name: agent_name
        type: string
        description: "Agent to use (default: general-chat)"
      - name: title
        type: string
        description: Optional session title
  - name: admin_workspace_dashboard
    file: dashboard.py
    function: dashboard
    bound: True
    description: Get or update a workspace's dashboard
    parameters:
      - name: workspace_pk
        type: integer
        description: Optional workspace primary key
      - name: content
        type: string
        description: Optional content to write
commands: []
---