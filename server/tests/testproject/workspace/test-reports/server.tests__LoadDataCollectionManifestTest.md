# Test Report

**Total:** 5 &nbsp;|&nbsp; **PASS:** 5 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_load_set_from_yaml` ✅

**Status:** `PASS`

A set YAML file from .agentone/sets/ loads with collection_type='set' and correctly parses set-specific fields like member_field.

---

### 2. `test_load_set_with_reprocess_config` ✅

**Status:** `PASS`

Sets with reprocess configuration (max_reprocess, member_field) are loaded correctly.

---

### 3. `test_load_stream_from_yaml` ✅

**Status:** `PASS`

A stream YAML file from .agentone/streams/ loads correctly. The directory name determines collection_type='stream', and all YAML frontmatter fields are parsed faithfully.

---

### 4. `test_missing_name_raises` ✅

**Status:** `PASS`

A YAML file without a 'name' field raises ValueError with a descriptive message. Prevents creation of unnamed collections.

---

### 5. `test_upsert_updates_existing` ✅

**Status:** `PASS`

Loading the same YAML file twice updates the existing DB record (same PK) rather than creating a duplicate. Idempotent reload is safe.

---
