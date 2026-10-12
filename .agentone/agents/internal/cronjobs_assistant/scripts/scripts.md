---
group: cronjobs
tools:
  # List cron jobs in the managed project scope
  - name: list_cronjobs
    file: cronjobs.py
    function: list_cronjobs
    bound: True

  # Create a new cron job (DB + .md file)
  - name: create_cronjob
    file: cronjobs.py
    function: create_cronjob
    bound: True

  # Collection health: counts by state + next run
  - name: cronjobs_stats
    file: cronjobs.py
    function: cronjobs_stats
    bound: True

  # Archive or restore a cron job
  - name: set_cronjob_archived
    file: cronjobs.py
    function: set_cronjob_archived
    bound: True
---
