---
name: collector
description: >
  Upstream data-flow agent — collect.* tasks (health_check, status) generate
  source data for integration tests. Tests cron→AgentTaskCall→CollectionItem
  pipeline. Used by SystemValidationTest.
tasks: [collect.*]
---
System validation collector agent
