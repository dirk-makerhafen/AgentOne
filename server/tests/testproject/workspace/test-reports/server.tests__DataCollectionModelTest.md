# Test Report

**Total:** 10 &nbsp;|&nbsp; **PASS:** 10 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_collection_type_choices` ✅

**Status:** `PASS`

Checks that both COLLECTION_TYPES choices are legal and produce the correct display labels.

---

### 2. `test_create_set` ✅

**Status:** `PASS`

Creates a set-type DataCollection with non-default values for every optional field. Confirms sources, processor, on_removed, member_field, and max_reprocess are all stored faithfully.

---

### 3. `test_create_stream` ✅

**Status:** `PASS`

Creates a stream-type DataCollection with all default values. Verifies name, type, active state, and every field has the expected default. Ensures new collections are immediately usable.

---

### 4. `test_description_default_blank` ✅

**Status:** `PASS`

Confirms description defaults to empty string, not None.

---

### 5. `test_is_active_default_true` ✅

**Status:** `PASS`

New collections are active by default so they participate in data-flow dispatch immediately.

---

### 6. `test_is_active_false` ✅

**Status:** `PASS`

Inactive collections can be created explicitly. The dispatch logic skips these.

---

### 7. `test_sources_json_round_trip` ✅

**Status:** `PASS`

Verifies JSON serialization round-trip for the sources field. MySQL JSONField stores and retrieves complex multi-entry source lists intact.

---

### 8. `test_str_set` ✅

**Status:** `PASS`

Verifies the human-readable string representation for ordered-set collections.

---

### 9. `test_str_stream` ✅

**Status:** `PASS`

Verifies the human-readable string representation for stream collections. Used in UI and log output.

---

### 10. `test_unique_name` ✅

**Status:** `PASS`

Verifies that the unique constraint on DataCollection.name rejects duplicate names at the DB level. Duplicates would cause data corruption in YAML-based name lookups.

---
