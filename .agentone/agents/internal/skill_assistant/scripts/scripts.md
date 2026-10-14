---
group: skill
tools:
  # Key details of ONE skill in one call (version, totals, counts)
  - name: skill_details
    file: skill.py
    function: skill_details
    bound: True

  # Report how ONE skill is used (loads by agent, recent loads)
  - name: skill_usage
    file: skill.py
    function: skill_usage
    bound: True

  # List the skills effectively available to one agent
  - name: skills_for_agent
    file: skill.py
    function: skills_for_agent
    bound: True

  # List ONE skill's child skills (<skill_dir>/skills/)
  - name: list_skills
    file: skill.py
    function: list_skills
    bound: True

  # List the agents owned by ONE skill (<skill_dir>/agents/)
  - name: list_agents
    file: skill.py
    function: list_agents
    bound: True
---
