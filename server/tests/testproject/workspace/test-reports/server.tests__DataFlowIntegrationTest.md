# Test Report

End-to-end: YAML loader → dispatch → propagate → reprocess.

**Total:** 1 &nbsp;|&nbsp; **PASS:** 1 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_03_multiple_calls_create_multiple_items` ✅

**Status:** `PASS`

Multiple completed calls produce items in the stream. Each call gets its own item with a unique content-based member hash.

---
