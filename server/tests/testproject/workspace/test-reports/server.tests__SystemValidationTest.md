# Test Report

End-to-end validation of the AgentOne data-flow framework.

    Tests are numbered to run in order (01 … 27).  Each test is wrapped in a
    transaction that is *committed* (not rolled back) so that later tests can
    see the side-effects.  This mirrors real-world usage where state
    accumulates across ticks.

**Total:** 7 &nbsp;|&nbsp; **PASS:** 7 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_01_manifests_load_correctly` ✅

**Status:** `PASS`

All 9 YAML manifests (3 streams, 4 sets, 1 cron, 2 agents) load and produce correct DB records with proper types, sources, processors, and field values.

---

### 2. `test_02_loader_upsert_idempotent` ✅

**Status:** `PASS`

Re-loading YAML manifests does not duplicate DB records. The upsert logic correctly identifies and updates existing records.

---

### 3. `test_03_agent_tasks_resolved` ✅

**Status:** `PASS`

Agent manifest loader resolved collect.* and report.* glob patterns into concrete TaskDefinitionVersion records for both the collector and reporter agents.

---

### 4. `test_06_dispatch_skips_non_matching_calls` ✅

**Status:** `PASS`

Calls that do not match the source agent/function criteria are not dispatched. A 'status' call does not create items in the health_events stream.

---

### 5. `test_19_retroactive_on_source_change_dispatches` ✅

**Status:** `PASS`

retroactive_on_source_change field persists correctly and is present on the model schema.

---

### 6. `test_20_empty_sources_does_not_crash` ✅

**Status:** `PASS`

Dispatch handles empty sources gracefully without crashing.

---

### 7. `test_25_propagate_skips_item_without_source_call` ✅

**Status:** `PASS`

Propagation skips CollectionItems with source_call=None — no derived items are created.

---
