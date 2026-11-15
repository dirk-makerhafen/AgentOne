# Test Report

End-to-end validation of the AgentOne data-flow framework.

    Tests are numbered to run in order (01 … 27).  Each test is wrapped in a
    transaction that is *committed* (not rolled back) so that later tests can
    see the side-effects.  This mirrors real-world usage where state
    accumulates across ticks.

**Total:** 1 &nbsp;|&nbsp; **PASS:** 1 &nbsp;|&nbsp; **FAIL:** 0

---

### 1. `test_03_agent_tasks_resolved` ✅

**Status:** `PASS`

Agent manifest loader resolved collect.* and report.* glob patterns into concrete TaskDefinitionVersion records for both the collector and reporter agents.

---
