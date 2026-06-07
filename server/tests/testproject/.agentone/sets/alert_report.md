---
name: alert_report
type: set
description: Graded alert report with severity-based dedup
sources:
  - type: stream
    stream: health_events
processor:
  agent: reporter
  function: report
member_field: "item.get('severity', 'info')"
score_field: "float(item.get('timestamp', 0))"
on_removed:
  agent: reporter
  function: cleanup
max_reprocess: 100
---
