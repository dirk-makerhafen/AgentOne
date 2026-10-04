---
name: hooks_child
description: >
  Fixture agent extending hooks_ok: overrides the reflect hook entry,
  inherits the rest. Used by LoadHooksTest.
extends: [hooks_ok]
hooks:
  - name: reflect
    on: stop
    task: distill_turn_v2
  - name: idle-watch
    on: session_end
    task: write_journal
---
Hooks inheritance fixture agent
