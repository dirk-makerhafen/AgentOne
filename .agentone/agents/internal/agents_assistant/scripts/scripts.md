---
group: agents
tools:
  # List agents visible in the managed scope
  - name: list_agents
    file: agents.py
    function: list_agents
    bound: True

  # Collection health: counts by visibility and kind
  - name: agents_stats
    file: agents.py
    function: agents_stats
    bound: True

  # Create a new agent manifest in the managed scope
  - name: create_agent
    file: agents.py
    function: create_agent
    bound: True

  # Reload all agents in the managed scope from disk
  - name: refresh_from_disk
    file: agents.py
    function: refresh_from_disk
    bound: True

  # Reload all agents in the managed scope from disk
  - name: refresh_from_disk
    file: agents.py
    function: refresh_from_disk
    bound: True
---
