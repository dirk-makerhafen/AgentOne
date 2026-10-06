---
group: execution
tools:
  - name: python
    file: python.py
    function: python
    bound: False
  - name: shell
    file: shell.py
    function: shell
    bound: False
  - name: kill
    file: kill.py
    function: kill
    bound: False
  - name: terminal_exec
    file: terminal.py
    function: terminal_exec
    bound: True
    access: write
  - name: terminal_send
    file: terminal.py
    function: terminal_send
    bound: True
    access: write
  - name: terminal_poll
    file: terminal.py
    function: terminal_poll
    bound: True
    access: read
  - name: terminal_list
    file: terminal.py
    function: terminal_list
    bound: True
  - name: terminal_kill
    file: terminal.py
    function: terminal_kill
    bound: True
    access: write
---