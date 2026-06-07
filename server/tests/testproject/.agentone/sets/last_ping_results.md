---
name: last_ping_results
type: set
description: Ordered set of ping results keyed by session
sources:
  - type: stream
    stream: ping_events
processor:
  agent: base
  function: write
member_field: "item.get('session', 'unknown')"
score_field: "float(item.get('timestamp', 0))"
on_removed:
  agent: base
  function: delete
---
