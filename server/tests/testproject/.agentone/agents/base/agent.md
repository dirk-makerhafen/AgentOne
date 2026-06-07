---
name: base
description: >
  Canonical baseline agent. fs.* tools (read/write/delete/tree), ping command,
  core_task — tests group-wildcard resolution, command whitelisting, and
  allowed-tool/command lists. Used by LoaderTest, RuntimeAgentTest,
  RuntimeSessionTest, DataFlowTest.
tools: [fs.*]
tasks: [core.*]
commands: [ping]
---
Base test agent
