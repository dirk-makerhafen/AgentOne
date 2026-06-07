# Test Report

End-to-end: YAML loader → dispatch → propagate → reprocess.

**Total:** 6 &nbsp;|&nbsp; **PASS:** 6 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_01_loader_creates_records` ✅

**Status:** `PASS`

The YAML loader creates DataCollection records in the database with the correct types.

---

### 2. `test_02_dispatch_creates_items` ✅

**Status:** `PASS`

Dispatch processes completed calls matching stream sources and creates CollectionItems with auto-generated 32-char member hashes and float scores.

---

### 3. `test_03_multiple_calls_create_multiple_items` ✅

**Status:** `PASS`

Multiple completed calls produce items in the stream. Each call gets its own item with a unique content-based member hash.

---

### 4. `test_04_propagate_to_derived_flow` ✅

**Status:** `PASS`

New items added to the ping_events stream propagate to the derived last_ping_results set via _propagate_from_collections.

---

### 5. `test_05_reprocess_set_preserves_unique_members` ✅

**Status:** `PASS`

Reprocessing a set re-creates items from matched calls. The (collection, member) unique constraint prevents duplicates.

---

### 6. `test_06_loader_upsert_idempotent` ✅

**Status:** `PASS`

Re-loading the same YAML files does not create duplicate DataCollection records. The upsert logic correctly identifies and updates existing records.

---
