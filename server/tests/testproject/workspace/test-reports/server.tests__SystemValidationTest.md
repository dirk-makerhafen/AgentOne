# Test Report

End-to-end validation of the AgentOne data-flow framework.

    Tests are numbered to run in order (01 … 27).  Each test is wrapped in a
    transaction that is *committed* (not rolled back) so that later tests can
    see the side-effects.  This mirrors real-world usage where state
    accumulates across ticks.

**Total:** 5 &nbsp;|&nbsp; **PASS:** 5 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_03_agent_tasks_resolved` ✅

**Status:** `PASS`

Agent manifest loader resolved collect.* and report.* glob patterns into concrete TaskDefinitionVersion records for both the collector and reporter agents.

---

### 2. `test_04_cron_execution_creates_call` ✅

**Status:** `PASS`

execute_cron_job creates an AgentTaskCall for the configured agent and function, updates last_run_at, total_runs, and next_run_at tracking fields.

---

### 3. `test_06_dispatch_skips_non_matching_calls` ✅

**Status:** `PASS`

Calls that do not match the source agent/function criteria are not dispatched. A 'status' call does not create items in the health_events stream.

---

### 4. `test_17_on_removed_handler_creates_call` ✅

**Status:** `PASS`

on_removed handler fires when a set item is removed during reprocess. An additional AgentTaskCall is created for the cleanup handler.

---

### 5. `test_25_propagate_skips_item_without_source_call` ✅

**Status:** `PASS`

Propagation skips CollectionItems with source_call=None — no derived items are created.

---
