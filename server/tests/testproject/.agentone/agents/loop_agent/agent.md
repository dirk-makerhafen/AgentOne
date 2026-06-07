---
name: loop_agent
description: >
  Tests end-to-end ordered-set pipeline with real processor Python functions
  (append_processed, filter_zero, filter_one, cleanup) loaded from
  scripts/scripts.md. Verifies stream→set transformation, set→set filtering,
  member_field/score_field extraction from processor results, and on_removed
  callbacks. Used by OrderedSetPipelineTest.
tasks: [loop_agent.*]
---
