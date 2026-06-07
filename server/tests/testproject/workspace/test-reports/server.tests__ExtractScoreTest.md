# Test Report

**Total:** 3 &nbsp;|&nbsp; **PASS:** 3 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_set_no_expr_returns_timestamp` ✅

**Status:** `PASS`

When no score_field expression is configured, sets also fall back to timestamp.

---

### 2. `test_set_returns_float_from_expr` ✅

**Status:** `PASS`

Sets evaluate the score_field expression to produce a float score. Here 'ts' is extracted from the arguments.

---

### 3. `test_stream_returns_timestamp` ✅

**Status:** `PASS`

Streams auto-generate a Unix timestamp as score, ensuring items are ordered by creation time by default.

---
