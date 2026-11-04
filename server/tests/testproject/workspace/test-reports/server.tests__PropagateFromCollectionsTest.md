# Test Report

**Total:** 3 &nbsp;|&nbsp; **PASS:** 3 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_propagate_picks_up_recent_item` ✅

**Status:** `PASS`

A recent item in the source stream (within the 30s window) is propagated to the derived stream that sources from it.

---

### 2. `test_propagate_set_source` ✅

**Status:** `PASS`

Set-type sources also propagate their new items to derived flows. Both stream→derived and set→derived propagation work.

---

### 3. `test_propagate_skips_old_item` ✅

**Status:** `PASS`

Items older than the 30s propagation window are skipped. This prevents re-processing of stale items on every tick.

---
