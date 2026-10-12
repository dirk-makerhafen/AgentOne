---
group: projects_mgmt
tools:
  # Show ONE project in depth (defaults to the session's project)
  - name: describe_project
    file: projects.py
    function: describe_project
    bound: True

  # Cross-project health overview with owned-record counts
  - name: projects_stats
    file: projects.py
    function: projects_stats
    bound: True
---
