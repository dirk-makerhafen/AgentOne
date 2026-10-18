---
name: vis_subagent
description: >
  Subagent-only fixture agent. Hidden from user pickers but spawnable.
  Lists vis_internal as a subagent so the spawn guard can be tested.
  Used by LoadVisibilityTest.
visibility: subagent
subagents:
  - name: vis_internal
    create: both
  - name: vis_mixin
    create: both
---
Subagent fixture agent
