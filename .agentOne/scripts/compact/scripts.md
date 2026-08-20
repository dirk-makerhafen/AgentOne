---
group: compact
commands:
  - name: compact
    file: compact_command.py
    function: compact
    bound: True
tasks:
  - name: build_llm_compact_context
    file: build_llm_compact_context.py
    function: build_llm_compact_context
    bound: True
  - name: ingest_compaction
    file: ingest_compaction.py
    function: ingest_compaction
    bound: True
  - name: compact_turn
    type: chain
    chain:
      - build_llm_compact_context
      - ingest_compaction
---

description