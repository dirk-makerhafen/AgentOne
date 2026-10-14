---
group: skill
tools:
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
---
