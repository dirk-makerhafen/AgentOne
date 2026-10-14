---
group: project
tools:
  # List THIS project's agents (<project>/.agentone/agents/)
  - name: list_agents
    file: project.py
    function: list_agents
    bound: True

  # List THIS project's skills (<project>/.agentone/skills/)
  - name: list_skills
    file: project.py
    function: list_skills
    bound: True

  # List THIS project's cron jobs (<project>/.agentone/cronjobs/)
  - name: list_cronjobs
    file: project.py
    function: list_cronjobs
    bound: True
---
