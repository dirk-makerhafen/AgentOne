---
group: skills_mgmt
tools:
  # List skills visible in the managed scope
  - name: list_skills
    file: skills.py
    function: list_skills
    bound: True

  # Give an agent a skill (live until next reload)
  - name: assign_skill
    file: skills.py
    function: assign_skill
    bound: True

  # Take a skill away from an agent (live until next reload)
  - name: unassign_skill
    file: skills.py
    function: unassign_skill
    bound: True
---
