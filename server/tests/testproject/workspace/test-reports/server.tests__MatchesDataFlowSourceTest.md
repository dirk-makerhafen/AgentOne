# Test Report

**Total:** 15 &nbsp;|&nbsp; **PASS:** 15 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_match_agent_and_function` ✅

**Status:** `PASS`

Query source matches when both agent and function globs match the call's properties.

---

### 2. `test_match_agent_glob` ✅

**Status:** `PASS`

Agent patterns support glob matching (test-* matches test-agent).

---

### 3. `test_match_project` ✅

**Status:** `PASS`

Project filter correctly matches calls belonging to the specified project.

---

### 4. `test_match_session` ✅

**Status:** `PASS`

Session pattern matching works when call's session name matches.

---

### 5. `test_multiple_agent_patterns_any_match` ✅

**Status:** `PASS`

When multiple agent patterns are given, any single match is sufficient (OR logic).

---

### 6. `test_no_match_agent` ✅

**Status:** `PASS`

Non-matching agent pattern correctly rejects the call.

---

### 7. `test_no_match_function` ✅

**Status:** `PASS`

Non-matching function pattern correctly rejects the call.

---

### 8. `test_no_match_project` ✅

**Status:** `PASS`

Non-matching project filter correctly rejects calls from other projects.

---

### 9. `test_no_match_session` ✅

**Status:** `PASS`

Non-matching session pattern correctly rejects the call.

---

### 10. `test_no_patterns_match_anything` ✅

**Status:** `PASS`

A source definition with no agent/function patterns matches all completed calls.

---

### 11. `test_set_type_handled_by_propagation` ✅

**Status:** `PASS`

Set-type sources return False from _matches_data_flow_source because they are handled by _propagate_from_collections instead.

---

### 12. `test_stream_type_handled_by_propagation` ✅

**Status:** `PASS`

Stream-type sources return False from _matches_data_flow_source because they are handled by _propagate_from_collections instead.

---

### 13. `test_string_pattern_instead_of_list` ✅

**Status:** `PASS`

Single string patterns work in addition to list patterns. The code wraps single strings in a list.

---

### 14. `test_unknown_type_returns_false` ✅

**Status:** `PASS`

Unknown source types are safely rejected with False.

---

### 15. `test_wildcard_agent` ✅

**Status:** `PASS`

Wildcard agent (*) matches any agent name.

---
