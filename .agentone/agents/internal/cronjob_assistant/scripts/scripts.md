---
group: cronjob
tools:
  # Show the full configuration of one cron job
  - name: cronjob_details
    file: cronjob.py
    function: cronjob_details
    bound: True

  # Edit schedule, agent, message, etc. of one cron job
  - name: edit_cronjob
    file: cronjob.py
    function: edit_cronjob
    bound: True

  # Enable or pause one cron job
  - name: set_cronjob_active
    file: cronjob.py
    function: set_cronjob_active
    bound: True

  # Show recent executions of one cron job
  - name: cronjob_runs
    file: cronjob.py
    function: cronjob_runs
    bound: True
---
