# Test Report

**Total:** 2 &nbsp;|&nbsp; **PASS:** 2 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_reprocess_collection_not_found` ✅

**Status:** `PASS`

Reprocessing a non-existent collection logs an error and returns gracefully without crashing.

---

### 2. `test_reprocess_no_source_calls` ✅

**Status:** `PASS`

Reprocessing a collection with no matching source calls produces no items. The task is a no-op when there are no inputs.

---
