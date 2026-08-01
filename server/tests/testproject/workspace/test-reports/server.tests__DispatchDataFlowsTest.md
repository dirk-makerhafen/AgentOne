# Test Report

**Total:** 3 &nbsp;|&nbsp; **PASS:** 3 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_dispatch_respects_source_criteria` ✅

**Status:** `PASS`

Calls that do not match the source criteria (wrong agent) are not dispatched. Source filtering is precise.

---

### 2. `test_dispatch_skips_inactive_flow` ✅

**Status:** `PASS`

Inactive (is_active=False) collections are skipped entirely during dispatch. No items are created even when source criteria match.

---

### 3. `test_dispatch_skips_no_query_source` ✅

**Status:** `PASS`

Dispatch only processes collections with query-type sources. Stream/set-type sources are handled by _propagate_from_collections instead.

---
