---
name: reflection-mixin
description: >
  Mixin that adds self-reflection hooks to an agent. Runs a detached
  reflection pass on compaction (pre_compact) and session end (session_end),
  producing a diagnostic report. Inherit via `extends` to opt in.
visibility: mixin
model: Qwen3.6-35B-A3B-UD-MLX-4bit
extends: []
tasks: [+, reflection.*]
hooks:
  - name: reflect-on-compact
    on: pre_compact
    task: reflect_session
    mode: detached
  - name: reflect-on-session-end
    on: session_end
    task: reflect_session
    mode: detached
---
You are a reflection agent. The reflection prompt is delivered as a user message at run time.
Do not continue any task; observe and report. Call final_result with your report.
