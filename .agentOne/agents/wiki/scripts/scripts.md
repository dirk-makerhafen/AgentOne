---
commands:
  - name: ingest_next
    file: ingest.py
    function: ingest_next
    bound: True
  - name: ingest_file
    file: ingest.py
    function: ingest_file
    bound: True
tasks:
  - name: verify
    file: ingest.py
    function: verify
    bound: True
  - name: ingest_verification_result
    file: ingest.py
    function: ingest_verification_result
    bound: True
  - name: ingest_unlinked_raw_results
    file: ingest.py
    function: ingest_unlinked_raw_results
    bound: True
---