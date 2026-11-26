---
name: full_settings
description: >
  Full agent.md settings snapshot used by LoaderTest and RuntimeAgentTest.
  Covers every frontmatter setting the loader maps to SettingsModel that does
  not need an external DB fixture (model rows, skills, hooks are tested in
  their own agents).
model: default
visibility: user
maxRetries: 3
maxTurns: 10
maxUnattendedTurns: 5
maxHistoryMessages: 50
autoCompactMaxTokens: 123456
autoCompactMinTokens: 4096
autoCompactIdleSeconds: 300
autoCompactKeepPercent: 12
schedulerStrategy: queue
toolCallSyntax: default
reasoningEffort: high
precision: focused
priority: 5
thinking: true
inheritSystemPrompt: false
subagentResultDelivery: immediate
commands: [ping, pong]
disallowedCommands: [unknown_command]
tasks: [core_task]
disallowedTasks: [unknown_task]
skills: []
disallowedSkills: []
tools: [read, write]
disallowedTools: [delete]
subagents: [base]
disallowedSubagents: [unknown_agent]
loadGuidanceFileIndex: true
guidanceFileIndexLimit: 12
autoload:
  files: [AGENTS.md, CLAUDE.md]
  maxFiles: 2
  maxChars: 1024
  maxCharsPerFile: 512
memoryPlaybook:
  enabled: true
  maxDirectives: 5
  maxChars: 200
  includeCandidates: true
  includeSkills: true
  maxSkills: 2
access:
  workspace:
    write:
      default: deny
routePin: auto
routeFailover: models
routeTarget: auto:best-free
routeWaitSeconds: 7
routeConstraints:
  free_only: true
  local_only: false
  prefer_free: true
  prefer_low_load: false
  require_tools: true
  min_tier: strong
  min_context: 4096
  providers_allow: [p1]
  providers_deny: [p2]
  exclude_models: [Beta]
localOnly: false
sessionBootstrap: |
  Workspace: {{workspace_dir}}
---
Agent with all scalar settings
