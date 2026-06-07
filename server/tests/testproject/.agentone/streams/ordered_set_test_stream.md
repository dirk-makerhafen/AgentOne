---
name: ordered_set_test_stream
description: Captures all generate_message calls for ordered-set testing
sources:
  - type: query
    agent: [loop_agent]
    function: [generate_message]
processor:
  agent: loop_agent
  function: append_processed
---
