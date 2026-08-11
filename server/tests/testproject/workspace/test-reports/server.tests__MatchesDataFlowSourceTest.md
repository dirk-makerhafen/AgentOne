# Test Report

**Total:** 5 &nbsp;|&nbsp; **PASS:** 5 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_match_agent_and_function` ✅

**Status:** `PASS`

Query source matches when both agent and function globs match the call's properties.

---

### 2. `test_match_agent_glob` ✅

**Status:** `PASS`

Agent patterns support glob matching (test-* matches test-agent).

---

### 3. `test_multiple_agent_patterns_any_match` ✅

**Status:** `PASS`

When multiple agent patterns are given, any single match is sufficient (OR logic).

---

### 4. `test_no_match_agent` ✅

**Status:** `PASS`

Non-matching agent pattern correctly rejects the call.

---

### 5. `test_wildcard_agent` ✅

**Status:** `PASS`

Wildcard agent (*) matches any agent name.

---
