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
---
