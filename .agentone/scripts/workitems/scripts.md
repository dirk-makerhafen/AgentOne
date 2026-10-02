---
group: workitems
tools:
  - name: workitem_create
    file: workitem_action.py
    function: workitem_create
    bound: True
  - name: workitem_update
    file: workitem_action.py
    function: workitem_update
    bound: True
  - name: workitem_list
    file: workitem_action.py
    function: workitem_list
    bound: True
  - name: workitem_add_child
    file: workitem_action.py
    function: workitem_add_child
    bound: True
---
Durable work items — long-term tasks that outlive the turn, dispatch to an
agent on their own, and can be checked by a reviewer. The scheduler owns
dispatch and verification; these tools only shape intent.

NOTE FOR MAINTAINERS: only the prose *below* this line is documentation. The
loader reads the YAML frontmatter above and derives each tool's LLM-visible
description from the function's Python docstring, so nothing here reaches a
model. Agent-facing guidance has to live in the docstrings in
`workitem_action.py`; keep the two in step when you change either.
