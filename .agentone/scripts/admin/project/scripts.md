---
group: admin
tools:
  - name: list
    file: list.py
    function: list_projects
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
  - name: reload
    file: reload.py
    function: reload
    bound: True
  - name: dashboard
    file: dashboard.py
    function: dashboard
    bound: True
tasks:
  - name: admin_project_list
    file: list.py
    function: list_projects
    bound: True
    description: List all projects in current scope
  - name: admin_project_stats
    file: stats.py
    function: stats
    bound: True
    description: Get cross-project statistics
  - name: admin_project_details
    file: details.py
    function: details
    bound: True
    description: Get detailed information about a project
    parameters:
      - name: project_pk
        type: integer
        description: Optional project primary key (defaults to current scope)
  - name: admin_project_create
    file: create.py
    function: create
    bound: True
    description: Create a new project
    parameters:
      - name: name
        type: string
        description: Project name (required, globally unique)
      - name: path
        type: string
        description: Optional filesystem path for project root
      - name: description
        type: string
        description: Optional description
      - name: manifest_in_workspace
        type: boolean
        description: If true and path is a workspace, put manifests in workspace
  - name: admin_project_reload
    file: reload.py
    function: reload
    bound: True
    description: Reload project manifests from disk
    parameters:
      - name: project_pk
        type: integer
        description: Optional project primary key (defaults to current scope)
  - name: admin_project_dashboard
    file: dashboard.py
    function: dashboard
    bound: True
    description: Get or update a project's dashboard
    parameters:
      - name: project_pk
        type: integer
        description: Optional project primary key
      - name: content
        type: string
        description: Optional content to write (if omitted, reads current)
commands: []
---