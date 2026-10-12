---
name: hooks_intercept
description: >
  Fixture agent declaring per-call intercept hooks. Used by intercept tests.
hooks:
  - name: guard-read
    match:
      name: "read"
      type: tool
    before: core_task
    mode: inline
  - name: trace-read
    match:
      name: "read"
      type: tool
    before: core_task
    mode: detached
  - name: audit-write
    match: "write*"
    after: core_task
    mode: detached
---
Intercept hooks fixture agent
