# Test Report

End-to-end validation of the AgentOne data-flow framework.

    Tests are numbered to run in order (01 … 27).  Each test is wrapped in a
    transaction that is *committed* (not rolled back) so that later tests can
    see the side-effects.  This mirrors real-world usage where state
    accumulates across ticks.

**Total:** 27 &nbsp;|&nbsp; **PASS:** 27 &nbsp;|&nbsp; **FAIL:** 0

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

### 4. `test_04_cron_execution_creates_call` ✅

**Status:** `PASS`

execute_cron_job creates an AgentTaskCall for the configured agent and function, updates last_run_at, total_runs, and next_run_at tracking fields.

---

### 5. `test_05_dispatch_to_stream_creates_items` ✅

**Status:** `PASS`

Completed AgentTaskCalls matching query-type sources produce CollectionItems with auto-generated 32-char member hashes and float timestamp scores.

---

### 6. `test_06_dispatch_skips_non_matching_calls` ✅

**Status:** `PASS`

Calls that do not match the source agent/function criteria are not dispatched. A 'status' call does not create items in the health_events stream.

---

### 7. `test_07_dispatch_to_set_creates_items` ✅

**Status:** `PASS`

Sets use user-defined member_field expressions. The member 'api' was extracted from the arguments via item.get('service', ...).

---

### 8. `test_08_set_dedup_update_or_create` ✅

**Status:** `PASS`

Two calls producing the same 'web' member result in only one CollectionItem due to the (collection, member) unique_together constraint.

---

### 9. `test_09_propagate_stream_to_stream` ✅

**Status:** `PASS`

New items added to health_events stream are propagated to parsed_alerts stream which sources from it via type:stream source.

---

### 10. `test_10_propagate_stream_to_set` ✅

**Status:** `PASS`

Items propagate from a stream to a set. The set's member_field expression extracts 'critical' from the source item's value.

---

### 11. `test_11_propagate_set_to_stream` ✅

**Status:** `PASS`

Items in a set propagate to derived streams that source from the set. Bidirectional stream↔set propagation works correctly.

---

### 12. `test_12_reprocess_stream_backfill` ✅

**Status:** `PASS`

reprocess_collection backfills 3 historical calls that match the query-type source criteria.

---

### 13. `test_13_reprocess_set_with_dedup_and_removal` ✅

**Status:** `PASS`

Reprocessing a set with 3 calls (2 sharing 'dup-1' member) produces exactly 2 unique items. Dedup via (collection, member) constraint works correctly.

---

### 14. `test_14_reprocess_respects_max_items` ✅

**Status:** `PASS`

max_items=2 limits reprocessing to at most 2 items, even though 5 calls exist.

---

### 15. `test_15_inactive_flow_skipped` ✅

**Status:** `PASS`

Inactive collections (is_active=False) are skipped during dispatch. No items created.

---

### 16. `test_16_set_score_field_eval` ✅

**Status:** `PASS`

score_field expression 'float(item.get("ts", 0))' evaluates to 42.5 from the call arguments.

---

### 17. `test_17_on_removed_handler_creates_call` ✅

**Status:** `PASS`

on_removed handler fires when a set item is removed during reprocess. An additional AgentTaskCall is created for the cleanup handler.

---

### 18. `test_18_type_set_source_propagation` ✅

**Status:** `PASS`

A collection with type:set source propagates items from the source set to the derived flow.

---

### 19. `test_19_retroactive_on_source_change_dispatches` ✅

**Status:** `PASS`

retroactive_on_source_change field persists correctly and is present on the model schema.

---

### 20. `test_20_empty_sources_does_not_crash` ✅

**Status:** `PASS`

Dispatch handles empty sources gracefully without crashing.

---

### 21. `test_21_no_processor_does_not_crash` ✅

**Status:** `PASS`

Dispatch handles missing processor config gracefully without crashing.

---

### 22. `test_22_multiple_sources_per_flow` ✅

**Status:** `PASS`

A flow with multiple query sources dispatches items from any matching source call.

---

### 23. `test_23_session_template_var_expansion` ✅

**Status:** `PASS`

The {source_session} template variable in processor session config expands to the source call's session name with '-copy' appended.

---

### 24. `test_24_retroactive_source_change_triggers_reprocess` ✅

**Status:** `PASS`

Changing sources with retroactive_on_source_change > 0 triggers reprocess and produces items from the new source criteria.

---

### 25. `test_25_propagate_skips_item_without_source_call` ✅

**Status:** `PASS`

Propagation skips CollectionItems with source_call=None — no derived items are created.

---

### 26. `test_26_type_set_source_propagation_from_yaml` ✅

**Status:** `PASS`

A YAML-loaded type:set source (alerts_from_report sourcing from alert_report) propagates items correctly through _propagate_from_collections.

---

### 27. `test_27_all_alerts_multi_source_propagation` ✅

**Status:** `PASS`

A multi-source stream (all_alerts with both stream and set sources) successfully propagates items from the health_events stream.

---
