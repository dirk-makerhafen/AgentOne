---
name: subagents_test
description: >
  Tests subagent config parsing — defines base subagent with create: both.
  Verifies subagentNames and subagent_config(). Used by LoaderTest and
  RuntimeAgentTest.
subagents:
  - name: base
    create: both
---
Agent with subagent config
