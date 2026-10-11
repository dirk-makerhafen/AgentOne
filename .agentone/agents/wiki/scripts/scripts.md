---
tools:
  - name: wiki_check
    file: wiki_checks.py
    function: wiki_check
    bound: True
  - name: find_unlinked_raw_files
    file: wiki_checks.py
    function: wiki_find_unlinked_raw
    bound: True
  - name: update_timeline
    file: update_timeline.py
    function: update_timeline
    bound: True
  - name: update_timeline_daily
    file: update_timeline_daily.py
    function: update_timeline_daily
    bound: True
  - name: update_timeline_monthly
    file: update_timeline_monthly.py
    function: update_timeline_monthly
    bound: True
  - name: update_entities
    file: update_entities.py
    function: update_entities
    bound: True
  - name: update_ingress
    file: update_ingress.py
    function: update_ingress
    bound: True
  - name: process_ingress
    file: process_ingress.py
    function: process_ingress
    bound: True

tasks:
  - name: find_unlinked_raw
    file: wiki_checks.py
    function: wiki_find_unlinked_raw
    bound: True
    max_retries: 3
    retry_delay: 30
  - name: update_timeline
    file: update_timeline.py
    function: update_timeline
    bound: True
    max_retries: 3
    retry_delay: 30
  - name: process_summary
    file: update_timeline.py
    function: process_summary
    bound: True
    max_retries: 3
    retry_delay: 30
  - name: double_check_summary
    file: update_timeline.py
    function: double_check_summary
    bound: True
    max_retries: 3
    retry_delay: 30
  - name: write_day_index
    file: update_timeline_daily.py
    function: write_day_index
    bound: True
  - name: write_month_index
    file: update_timeline_monthly.py
    function: write_month_index
    bound: True
  - name: write_entity
    file: update_entities.py
    function: write_entity
    bound: True
  - name: finalize_ingress_item
    file: process_ingress.py
    function: finalize_ingress_item
    bound: True
    max_retries: 3
    retry_delay: 30
    
commands:
  - name: ingest_next
    file: ingest.py
    function: ingest_next
    bound: True

  - name: sync_applemail
    file: sync_applemail.py
    function: sync

  - name: wiki_lint
    file: wiki_checks.py
    function: wiki_check
    bound: True
---