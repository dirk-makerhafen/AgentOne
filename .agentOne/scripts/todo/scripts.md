---
group: todo
tools:
  - name: todo_append
    file: todolist.py
    function: todo_append
    bound: True
  - name: todo_list
    file: todolist.py
    function: todo_list
    bound: True
  - name: todo_update
    file: todolist.py
    function: todo_update
    bound: True
  - name: todo_delete
    file: todolist.py
    function: todo_delete
    bound: True
  - name: todo_clear
    file: todolist.py
    function: todo_clear
    bound: True
commands:
  - name: todo_append
    file: todolist.py
    function: todo_append
    bound: True
  - name: todo_list
    file: todolist.py
    function: todo_list
    bound: True
  - name: todo_update
    file: todolist.py
    function: todo_update
    bound: True
  - name: todo_delete
    file: todolist.py
    function: todo_delete
    bound: True
  - name: todo_clear
    file: todolist.py
    function: todo_clear
    bound: True
tasks:
  - name: todolist_action
    file: todolist.py
    function: todolist_action
    bound: True
  - name: todolist_action_response
    file: todolist.py
    function: todolist_action_response
    bound: True
---
Session todo list. Items are event-sourced from the todolist_store call
history (no DB); auto-processing is user-controlled via the /todo command
or the Todos tab.
