---
group: wiki
tools:
  - name: wiki_init
    file: wiki_init.py
    function: wiki_init
    bound: True

  - name: wiki_ingest
    file: wiki_ingest.py
    function: wiki_ingest
    bound: True

  - name: wiki_query
    file: wiki_query.py
    function: wiki_query
    bound: True

  - name: wiki_lint
    file: wiki_lint.py
    function: wiki_lint
    bound: True

  - name: wiki_check
    file: wiki_checks.py
    function: wiki_check
    bound: True
tasks:
  - name: find_unlinked_raw
    file: wiki_checks.py
    function: wiki_find_unlinked_raw
    bound: True

commands:
  - name: wiki_lint
    file: wiki_checks.py
    function: wiki_check
    bound: True

---
