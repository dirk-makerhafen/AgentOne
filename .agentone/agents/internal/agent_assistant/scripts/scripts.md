---
group: agent
tools:
  # Report how ONE agent is used (sessions, crons, work items)
  - name: agent_usage
    file: agent.py
    function: agent_usage
    bound: True

  # List ONE agent's version history
  - name: agent_versions
    file: agent.py
    function: agent_versions
    bound: True
---
