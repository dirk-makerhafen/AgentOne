---
name: reflection-mixin
description: >
  Mixin that adds self-reflection hooks to an agent. Runs a detached
  reflection pass when the `session_end` task runs, and again before
  `compact_turn` drops context, producing a diagnostic report. Inherit via
  `extends` to opt in.
visibility: mixin
tasks: [+, reflection.*]
hooks:
  - name: reflect-on-session-end
    match:
      name: session_end
      session_type: "session | subsession | subtask_delegate | subtask_fork"
    after: reflect_session
    mode: detached
  - name: reflect-before-compact
    match:
      name: compact_turn
      session_type: "session | subsession | subtask_delegate | subtask_fork"
    before: reflect_session
    mode: detached
---
This mixin can not run standalone, system prompt comes from inheriting agent.