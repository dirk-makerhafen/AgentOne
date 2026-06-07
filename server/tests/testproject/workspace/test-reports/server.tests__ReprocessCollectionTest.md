# Test Report

**Total:** 7 &nbsp;|&nbsp; **PASS:** 7 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_reprocess_collection_not_found` ✅

**Status:** `PASS`

Reprocessing a non-existent collection logs an error and returns gracefully without crashing.

---

### 2. `test_reprocess_no_source_calls` ✅

**Status:** `PASS`

Reprocessing a collection with no matching source calls produces no items. The task is a no-op when there are no inputs.

---

### 3. `test_reprocess_query_source` ✅

**Status:** `PASS`

Reprocessing a collection with query-type sources finds completed calls matching the source criteria and creates CollectionItems.

---

### 4. `test_reprocess_respects_max_items` ✅

**Status:** `PASS`

The max_reprocess limit caps the number of items processed. Only 2 items are created even though 5 source calls exist.

---

### 5. `test_reprocess_set_removes_stale_item` ✅

**Status:** `PASS`

When a source call's arguments change, reprocessing clears old items and re-creates from the updated source calls. The stale item (member 'original') is removed and a new one (member 'changed') is created.

---

### 6. `test_reprocess_set_update_or_create_dedup` ✅

**Status:** `PASS`

When two source calls produce the same member (same 'id'), the set's (collection, member) unique constraint prevents duplicates. Only one item exists.

---

### 7. `test_reprocess_stream_source` ✅

**Status:** `PASS`

Reprocessing a collection with stream-type sources reads the source stream's items and re-dispatches them through the processor.

---
