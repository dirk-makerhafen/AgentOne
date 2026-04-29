---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.


name	    Yes	Unique identifier using lowercase letters and hyphens
description	Yes	When Claude should delegate to this subagent
tools	    No	Tools the subagent can use. Inherits all tools if omitted
disallowedTools	No	Tools to deny, removed from inherited or specified list
model	No	Model to use: sonnet, opus, haiku, a full model ID (for example, claude-opus-4-7), or inherit. Defaults to inherit
permissionMode	No	Permission mode: default, acceptEdits, auto, dontAsk, bypassPermissions, or plan
maxTurns	No	Maximum number of agentic turns before the subagent stops
skills	No	Skills to load into the subagent’s context at startup. The full skill content is injected, not just made available for invocation. Subagents don’t inherit skills from the parent conversation
mcpServers	No	MCP servers available to this subagent. Each entry is either a server name referencing an already-configured server (e.g., "slack") or an inline definition with the server name as key and a full MCP server config as value
hooks	No	Lifecycle hooks scoped to this subagent
memory	No	Persistent memory scope: user, project, or local. Enables cross-session learning
background	No	Set to true to always run this subagent as a background task. Default: false
effort	No	Effort level when this subagent is active. Overrides the session effort level. Default: inherits from session. Options: low, medium, high, xhigh, max; available levels depend on the model
isolation	No	Set to worktree to run the subagent in a temporary git worktree, giving it an isolated copy of the repository. The worktree is automatically cleaned up if the subagent makes no changes
color	No	Display color for the subagent in the task list and transcript. Accepts red, blue, green, yellow, purple, orange, pink, or cyan
initialPrompt	No	Auto-submitted as the first user turn when this agent runs as the main session agent (via --agent or the agent setting). Commands and skills are processed. Prepended to any user-provided prompt