---
name: no_match
description: >
  Error-handling test — references nonexistent task group. Loading must raise
  "No Task Definition found". Used by LoaderTest.
tools: [nonexistent.*]
---
Agent with unresolvable pattern — should fail loading
