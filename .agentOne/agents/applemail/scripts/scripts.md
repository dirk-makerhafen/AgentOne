---
commands:
  - name: sync_applemail
    map:
        - sync
        - email_received
tasks:
  - name: sync
    file: sync_applemail.py
    function: sync
  - name: email_received
    file: sync_applemail.py
    function: email_received
---

