# Test Report

End-to-end ordered-set integration tests using real YAML manifests.

**Total:** 3 &nbsp;|&nbsp; **PASS:** 3 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_populates_set_a_from_stream_via_reprocess` ✅

**Status:** `PASS`

Reprocessing the stream from 100 query-source calls produces 100 stream items; reprocessing set_a from those stream items evaluates member_field='str(item.get(\'num\', -1))' giving members '0'..'99'.

---

### 2. `test_set_a_member_field_dedup` ✅

**Status:** `PASS`

Two source calls with the same num=42 produce only one CollectionItem with member='42' because update_or_create deduplicates on (collection, member).

---

### 3. `test_set_to_set_filtering` ✅

**Status:** `PASS`

set_b's member_field keeps items with num<50 as unique members '0'..'49' and collapses all num>=50 items to member 'SKIP'. 51 total items.

---
