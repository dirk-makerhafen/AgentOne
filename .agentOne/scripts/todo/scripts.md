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
  - name: todo_pop
    file: todolist.py
    function: todo_pop
    bound: True
  - name: todo_peek
    file: todolist.py
    function: todo_peek
    bound: True
  - name: todo_done
    file: todolist.py
    function: todo_done
    bound: True
  - name: todo_remove
    file: todolist.py
    function: todo_remove
    bound: True
  - name: todo_clear
    file: todolist.py
    function: todo_clear
    bound: True
commands:
  - name: todo
    file: todolist.py
    function: todo_command
    bound: True
  - name: todo_append
    file: todolist.py
    function: todo_append
    bound: True
  - name: todo_clear
    file: todolist.py
    function: todo_clear
    bound: True
tasks:
  # Shared-history anchor — TASK-type so the LLM never sees it.  All todo
  # tools record their actions here; the call history IS the todo list.
  - name: todolist_store
    file: todolist.py
    function: todolist_store
    bound: True
---
Session todo list. Items are event-sourced from the todolist_store call
history (no DB); auto-processing is user-controlled via the /todo command
or the Todos tab.
