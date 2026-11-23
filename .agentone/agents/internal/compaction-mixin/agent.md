---
name: compaction-mixin
description: >
  Mixin that adds reactive context compaction to an agent. Installs an inline
  before-hook on decide_next_step: when the last LLM response crossed the
  auto-compact threshold the hook opens the session fence, forks a summary
  pass, and blocks the turn until the COMPACTION marker is in place. Inherit
  via `extends` to opt in; swap this mixin (or override `compact_if_needed`)
  to change the policy.
visibility: mixin
tasks: [+, compact.*]
commands: [+, compact]
toolCallSyntax: default

autoCompactMaxTokens: 125000
autoCompactMinTokens:  25000
autoCompactIdleSeconds: 1800
autoCompactKeepPercent: 0

hooks:
  - name: compact-before-decide
    match:
      name: decide_next_step
      session_type: "session | subsession | cronjob | subtask_delegate | subtask_fork"
    before: compact_if_needed
    mode: inline
---
This mixin can not run standalone, system prompt comes from inheriting agent.

