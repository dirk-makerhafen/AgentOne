---
name: set_b
type: set
description: Second ordered set — filter_one processor, simple member extraction
sources:
  - type: set
    set: set_a
processor:
  agent: loop_agent
  function: filter_one
member_field: "str(item.get('num', -1))"
score_field: "float(item.get('num', 0))"
on_removed:
  agent: loop_agent
  function: cleanup
max_reprocess: 200
---
