# Test Report

**Total:** 8 &nbsp;|&nbsp; **PASS:** 8 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_empty_pattern` ✅

**Status:** `PASS`

Empty pattern returns False as it cannot match anything.

---

### 2. `test_exact_match` ✅

**Status:** `PASS`

Exact string matching works for agent name patterns.

---

### 3. `test_exact_no_match` ✅

**Status:** `PASS`

Different names are correctly rejected.

---

### 4. `test_wildcard_match_all` ✅

**Status:** `PASS`

Single-asterisk wildcard matches any string — used for 'all agents'.

---

### 5. `test_wildcard_middle` ✅

**Status:** `PASS`

Wildcard in middle matches strings that start and end with the given patterns.

---

### 6. `test_wildcard_no_match` ✅

**Status:** `PASS`

Wildcard correctly rejects non-matching inputs.

---

### 7. `test_wildcard_prefix` ✅

**Status:** `PASS`

Prefix wildcard (*suffix) matches strings ending with the suffix.

---

### 8. `test_wildcard_suffix` ✅

**Status:** `PASS`

Suffix wildcard (prefix*) matches strings starting with the prefix.

---
