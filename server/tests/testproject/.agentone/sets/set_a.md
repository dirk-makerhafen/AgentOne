---
name: set_a
type: set
description: First ordered set — filter_zero processor, simple member extraction
sources:
  - type: stream
    stream: ordered_set_test_stream
processor:
  agent: loop_agent
  function: filter_zero
member_field: "str(item.get('num', -1))"
score_field: "float(item.get('num', 0))"
on_removed:
  agent: loop_agent
  function: cleanup
max_reprocess: 200
---
