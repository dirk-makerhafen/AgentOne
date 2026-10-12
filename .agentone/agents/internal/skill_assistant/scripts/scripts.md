---
group: skill
tools:
  # Show ONE skill in full, with the agents using it
  - name: describe_skill
    file: skill.py
    function: describe_skill
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
---
