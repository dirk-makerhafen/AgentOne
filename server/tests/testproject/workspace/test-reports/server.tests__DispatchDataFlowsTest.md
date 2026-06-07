# Test Report

**Total:** 6 &nbsp;|&nbsp; **PASS:** 6 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_dispatch_creates_collection_item` ✅

**Status:** `PASS`

A completed call matching query-type source criteria triggers _dispatch_data_flows to create exactly one CollectionItem in the target collection.

---

### 2. `test_dispatch_only_one_item_per_tick` ✅

**Status:** `PASS`

Only one item per flow per tick is dispatched (conservative throttling). Even when multiple calls match, only the first is processed. This prevents flooding during catch-up after downtime.

---

### 3. `test_dispatch_respects_source_criteria` ✅

**Status:** `PASS`

Calls that do not match the source criteria (wrong agent) are not dispatched. Source filtering is precise.

---

### 4. `test_dispatch_skips_inactive_flow` ✅

**Status:** `PASS`

Inactive (is_active=False) collections are skipped entirely during dispatch. No items are created even when source criteria match.

---

### 5. `test_dispatch_skips_no_query_source` ✅

**Status:** `PASS`

Dispatch only processes collections with query-type sources. Stream/set-type sources are handled by _propagate_from_collections instead.

---

### 6. `test_stream_auto_member_and_score` ✅

**Status:** `PASS`

Streams automatically generate a 32-char hash member and float timestamp score. No manual configuration is needed for stream items.

---
