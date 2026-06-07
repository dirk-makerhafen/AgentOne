---
name: parsed_alerts
description: Parsed/graded health check events
sources:
  - type: stream
    stream: health_events
processor:
  agent: reporter
  function: grade
---
