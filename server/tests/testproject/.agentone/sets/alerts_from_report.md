---
name: alerts_from_report
type: set
description: "Set that sources from the alert_report set (type: set source)"
sources:
  - type: set
    set: alert_report
processor:
  agent: reporter
  function: grade
member_field: "item.get('severity', str(item))"
score_field: "float(item.get('ts', 0))"
max_reprocess: 50
---
