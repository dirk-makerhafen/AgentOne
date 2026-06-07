---
name: file_changes
type: set
description: Tracks unique file paths that have been written
sources:
  - type: query
    agent: [base]
    function: [write, delete]
processor:
  agent: base
  function: tree
member_field: "item.get('path', str(item))"
score_field: "float(item.get('timestamp', 0))"
max_reprocess: 100
---
