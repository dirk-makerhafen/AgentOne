# Test Report

**Total:** 9 &nbsp;|&nbsp; **PASS:** 9 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_cascade_delete_collection` ✅

**Status:** `PASS`

Deleting a DataCollection cascades to delete all its items. Ensures no orphan CollectionItems remain.

---

### 2. `test_create_item` ✅

**Status:** `PASS`

Creates a minimal CollectionItem with all required fields and verifies defaults. source_call is None when not provided, as expected for manually created items.

---

### 3. `test_same_member_different_collection_ok` ✅

**Status:** `PASS`

The same member string is allowed in different collections. The unique constraint is scoped to (collection, member), not global.

---

### 4. `test_score_default` ✅

**Status:** `PASS`

Score defaults to 0.0 when not specified, ensuring numeric ordering always works.

---

### 5. `test_source_call_set_null_on_delete` ✅

**Status:** `PASS`

Deleting the source AgentTaskCall sets source_call to null (SET_NULL) rather than cascading. Preserves the collection item even when the producing call is cleaned up.

---

### 6. `test_str` ✅

**Status:** `PASS`

String representation includes collection name, member, and score for easy debugging.

---

### 7. `test_unique_together_collection_member` ✅

**Status:** `PASS`

Verifies the (collection, member) unique constraint prevents duplicate members within a collection. This is the core dedup mechanism for sets.

---

### 8. `test_value_default` ✅

**Status:** `PASS`

Value defaults to empty dict, ensuring JSONField operations don't fail on missing data.

---

### 9. `test_with_source_call` ✅

**Status:** `PASS`

Items can reference their producing AgentTaskCall. The reverse relation (call.collection_items) also works, enabling provenance tracking.

---
