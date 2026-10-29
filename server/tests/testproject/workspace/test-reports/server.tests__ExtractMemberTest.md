# Test Report

**Total:** 5 &nbsp;|&nbsp; **PASS:** 5 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_set_expr_error_falls_back_to_pk` ✅

**Status:** `PASS`

When the member_field expression raises an exception (undefined attribute), the code gracefully falls back to the call PK instead of crashing.

---

### 2. `test_set_returns_str_pk_when_no_expr` ✅

**Status:** `PASS`

Sets fall back to the AgentTaskCall PK as member when no member_field expression is configured.

---

### 3. `test_set_uses_expr` ✅

**Status:** `PASS`

Sets evaluate the member_field Python expression against the item value. Here 'msg' is extracted from {'msg': 'hello'}.

---

### 4. `test_stream_hash_deterministic` ✅

**Status:** `PASS`

The hash is deterministic — identical inputs produce identical members. Ensures dedup works correctly.

---

### 5. `test_stream_returns_hash` ✅

**Status:** `PASS`

Streams auto-generate a 32-character SHA-256 hex digest as member. This provides content-addressed dedup based on arguments+timestamp.

---
