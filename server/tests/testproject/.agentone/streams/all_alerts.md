---
name: all_alerts
description: "Stream sourced from multiple sources (health_events stream + alerts_from_report set)"
sources:
  - type: stream
    stream: health_events
  - type: set
    set: alerts_from_report
processor:
  agent: reporter
  function: report
---
