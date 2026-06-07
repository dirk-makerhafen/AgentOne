---
name: ping_events
description: Records all ping command invocations
sources:
  - type: query
    agent: [base]
    function: [ping]
processor:
  agent: base
  function: read
---
