# Test Report

End-to-end: YAML loader → dispatch → propagate → reprocess.

**Total:** 2 &nbsp;|&nbsp; **PASS:** 2 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_01_loader_creates_records` ✅

**Status:** `PASS`

The YAML loader creates DataCollection records in the database with the correct types.

---

### 2. `test_06_loader_upsert_idempotent` ✅

**Status:** `PASS`

Re-loading the same YAML files does not create duplicate DataCollection records. The upsert logic correctly identifies and updates existing records.

---
