---
name: full_settings
description: >
  Tests every scalar agent setting round-trips YAML→DB correctly. Verifies
  maxRetries, reasoningEffort, priority, subagentResultDelivery, etc.
  Used by LoaderTest and RuntimeAgentTest.
maxRetries: 3
maxTurns: 10
maxUnattendedTurns: 5
maxHistoryMessages: 50
schedulerStrategy: queue
toolCallSyntax: default
reasoningEffort: high
priority: 5
thinking: true
subagentResultDelivery: immediate
---
Agent with all scalar settings
