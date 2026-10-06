---
group: history
tools:
  # Search your own session history (full store, not just LLM context)
  - name: search_own_history
    file: search_own_history.py
    function: search_own_history
    bound: True

  # Full content of one message or tool call (drill-down for search hits)
  - name: inspect_history_item
    file: inspect_history_item.py
    function: inspect_history_item
    bound: True
---
