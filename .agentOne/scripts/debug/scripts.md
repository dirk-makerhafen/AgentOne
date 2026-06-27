---
group: debug
commands:
  - name: debug
    file: debug.py
    function: debug
    bound: True
  - name: test-approval
    file: debug.py
    function: debug
    bound: True
    requires_approval: true
---
