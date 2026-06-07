---
name: session_override
description: >
  Tools-only agent with no commands/tasks — verifies allowedCommandNames and
  allowedTaskNames return empty while tools resolve. Tests session-level
  disallowed overlays on tools-only agent. Used by RuntimeAgentTest,
  RuntimeSessionTest.
tools: [fs.*]
---
Agent for session override tests
