---
name: hooks_child
description: >
  Fixture agent extending hooks_ok: overrides one intercept entry, adds
  another. Kept as an inheritance fixture.
extends: [hooks_ok]
hooks:
  - name: guard-read
    match: {name: read, type: tool}
    before: core_task
    mode: detached
  - name: idle-watch
    match: {name: write}
    after: core_task
---
Hooks inheritance fixture agent
