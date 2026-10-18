---
group: agent
tools:
  # Key details of ONE agent in one call (version, totals, counts)
  - name: agent_details
    file: agent.py
    function: agent_details
    bound: True

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

  # List ONE agent's child skills (<agent_dir>/skills/)
  - name: list_skills
    file: agent.py
    function: list_skills
    bound: True

  # List ONE agent's subagents (<agent_dir>/agents/)
  - name: list_agents
    file: agent.py
    function: list_agents
    bound: True

  # List cron jobs targeting ONE agent
  - name: list_cronjobs
    file: agent.py
    function: list_cronjobs
    bound: True

  # Reload THIS agent (and children) from disk after manifest edits
  - name: refresh_from_disk
    file: agent.py
    function: refresh_from_disk
    bound: True
---
