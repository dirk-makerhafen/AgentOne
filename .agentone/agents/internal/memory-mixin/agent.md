---
name: memory-mixin
description: >
  Mixin that persists reflection and compaction reports into the memory tree
  the moment they are produced, instead of waiting for a later
  memory_walk(refresh=True). Installs detached after-hooks on
  ingest_reflection_result and ingest_compaction that capture the report and
  write it to the session's canonical reflections.md / compaction.md file.
  Inherit via extends to opt in.
visibility: mixin
tasks: [+, memory.*]
toolCallSyntax: default
hooks:
  - name: save-reflection-after-ingest
    match:
      name: ingest_reflection_result
      session_type: "session | subsession | subtask_delegate | subtask_fork | cronjob"
    after: persist_memory_report
    mode: detached
  - name: save-compaction-after-ingest
    match:
      name: ingest_compaction
      session_type: "session | subsession | subtask_delegate | subtask_fork | cronjob"
    after: persist_memory_report
    mode: detached
---
This mixin can not run standalone, system prompt comes from inheriting agent.