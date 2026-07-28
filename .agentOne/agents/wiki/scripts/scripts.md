---
commands:
  - name: ingest
    file: ingest.py
    function: ingest
    bound: True
tasks:
  - name: verify
    file: ingest.py
    function: verify
    bound: True
  - name: ingest_verification
    file: ingest.py
    function: ingest_verification
    bound: True
---