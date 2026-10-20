---
name: hooks_ok
description: >
  Fixture agent declaring intercept hooks. Used by hook loader tests.
hooks:
  - name: guard-read
    match: {name: read, type: tool}
    before: core_task
  - name: audit-write
    match: {name: "write*"}
    after: core_task
    mode: detached
---
Hooks fixture agent
