---
name: health_events
description: Raw health-check results from collector
sources:
  - type: query
    agent: [collector]
    function: [health_check]
processor:
  agent: reporter
  function: parse
---
