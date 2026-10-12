---
group: adhoc
tools:
  - name: adhoc_create
    file: adhoc.py
    function: adhoc_create
    bound: True
    access: write
  - name: adhoc_list
    file: adhoc.py
    function: adhoc_list
    bound: True
    access: read
  - name: adhoc_read
    file: adhoc.py
    function: adhoc_read
    bound: True
    access: read
  - name: adhoc_update
    file: adhoc.py
    function: adhoc_update
    bound: True
    access: write
  - name: adhoc_delete
    file: adhoc.py
    function: adhoc_delete
    bound: True
    access: write
  - name: adhoc_function_call
    file: adhoc.py
    function: adhoc_function_call
    bound: True
    access: write


  - name: template_list
    file: query_template.py
    function: template_list
    bound: True
  - name: template_get
    file: query_template.py
    function: template_get
    bound: True
  - name: template_save
    file: query_template.py
    function: template_save
    bound: True
  - name: template_delete
    file: query_template.py
    function: template_delete
    bound: True
  - name: template_render
    file: query_template.py
    function: template_render
    bound: True
  - name: template_execute
    file: query_template.py
    function: template_execute
    bound: True


---
Session-private throwaway helpers. Ad-hoc tools are single Python functions
that live only for this session (auto-inert on archive, gone with the
session folder) and are NEVER registered globally — `adhoc_function_call`
is the only way to run them. There is no promotion path in V1.
