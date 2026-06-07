---
name: disallowed
description: >
  Tests disallowedToolNames — delete and tree* blocked from fs.*. Also used by
  session tests for session-level disallowed overlays. Used by RuntimeAgentTest,
  RuntimeSessionTest.
tools: [fs.*, compiler.*]
disallowedTools: [delete, tree*]
---
Agent with disallowed tools
