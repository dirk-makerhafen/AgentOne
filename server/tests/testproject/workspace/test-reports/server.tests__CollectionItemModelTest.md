# Test Report

**Total:** 2 &nbsp;|&nbsp; **PASS:** 2 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_source_call_set_null_on_delete` ✅

**Status:** `PASS`

Deleting the source AgentTaskCall sets source_call to null (SET_NULL) rather than cascading. Preserves the collection item even when the producing call is cleaned up.

---

### 2. `test_with_source_call` ✅

**Status:** `PASS`

Items can reference their producing AgentTaskCall. The reverse relation (call.collection_items) also works, enabling provenance tracking.

---
