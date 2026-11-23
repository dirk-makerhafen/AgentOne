---
name: Reflection Beam 1.0 Free
developer: Reflection AI
canonical_id: reflection/beam-1.0-501b-a23b
leaderboard_id: beam-free
leaderboard_rank: 156
family: beam
context_window: 1048576
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
---

Reflection Beam 1.0 is a 501B-parameter sparse mixture-of-experts (MoE) model with 23B active parameters, designed for coding and agentic workflows. It combines strong coding capabilities with fast, low-latency inference through its MoE architecture.

**Capabilities:**

- Sparse MoE architecture: 501B total / 23B active parameters for efficient inference
- Reasoning with configurable effort levels (low, medium, high, xhigh, max)
- Tool/function calling support
- Structured output support
- Temperature control
- Text in / text out
- Up to 1M context window
- Open weights under Apache 2.0 (Reflection AI release)

**Notes:**

- Knowledge cutoff: 2026-06-30
- Release date: 2026-10-05 (updated 2026-10-16)
- Canonical model: `reflection/beam-1.0-501b-a23b`
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Data handling: Free endpoints may log usage; avoid personal/confidential data

**Sources**

- https://reflection.ai/blog/introducing-beam (official announcement)
- https://huggingface.co/reflection/Beam-1.0-501B-A23B (official weights)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)
- ../providers/openrouter.md (roster 2026-10-28)
- ../providers/kilo-code.md (catalog 2026-10-28)
