---
name: unique_services
type: set
description: Deduplicated service endpoints from health checks
sources:
  - type: query
    agent: [collector]
    function: [health_check]
processor:
  agent: reporter
  function: dedup
member_field: "item.get('service', str(item))"
score_field: "float(item.get('timestamp', 0))"
max_reprocess: 50
---
