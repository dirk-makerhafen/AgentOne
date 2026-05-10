---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.

NAME             REQUIRED   DESCRIPTION
name	           Yes	    Unique identifier using lowercase letters and hyphens
description	       Yes	    When AgentOne should delegate to this subagent
model	            No	    Model to use: sonnet, opus, haiku, a full model ID (for example, gemma4:e3b), or inherit. 
maxRetries          No      In case of error, how many retries do we do
maxTurns            No      Maximum number of agentic turns before the subagent stops
maxUnattendedTurns  No      Maximum number of agentic turns before the subagent requires human confirmation
maxHistoryMessages  No      Maximum number of historic messages the agent sees by default
executionMode       No      TODO
toolCallSyntax      No      Custom of default tool call syntax
skills      	    No	    Skills to load into the subagent’s context at startup. Subagents don’t inherit skills from the parent conversation
disallowedSkills    No	    Skills to deny, removed from inherited or specified list
tools	            No	    Tools the agent can use. Inherits all tools if omitted
disallowedTools	    No	    Tools to deny, removed from inherited or specified list
tasks	            No	    Tasks the system can use, Inherits all tasks from parent
disallowedTasks	    No	    Tasks to deny, removed from inherited or specified list
commands	        No	    Commands the user can use, Inherits all commands from parent
disallowedCommands  No	    Commands to deny, removed from inherited or specified list




permissionMode	No	Permission mode: default, acceptEdits, auto, dontAsk, bypassPermissions, or plan

hooks	No	Lifecycle hooks scoped to this subagent
memory	No	Persistent memory scope: user, project, or local. Enables cross-session learning
background	No	Set to true to always run this subagent as a background task. Default: false
effort	No	Effort level when this subagent is active. Overrides the session effort level. Default: inherits from session. Options: low, medium, high, xhigh, max; available levels depend on the model
isolation	No	Set to worktree to run the subagent in a temporary git worktree, giving it an isolated copy of the repository. The worktree is automatically cleaned up if the subagent makes no changes
initialPrompt	No	Auto-submitted as the first user turn when this agent runs as the main session agent (via --agent or the agent setting). Commands and skills are processed. Prepended to any user-provided prompt


self.task_prompt = textwrap.dedent(task_prompt).strip() if task_prompt else None
self.system_prompt = textwrap.dedent(system_prompt).strip() if system_prompt else None
self.extra_settings = extra_settings
self.priority = priority
self.variants = variants
self.thinking = thinking
