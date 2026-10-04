---
name: hooks_ok
description: >
  Fixture agent declaring session hooks. Used by LoadHooksTest.
hooks:
  - name: reflect
    on: stop
    matcher: session
    task: distill_turn
    ingest: record_memory
    max_tokens: 10000
    timeout_seconds: 60
  - on: post_compact
    task: archive_transcript
  - on: session_end
    task: write_journal
    timeout_seconds: 120
---
Hooks fixture agent
