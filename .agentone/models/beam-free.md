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
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: beam-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
  - name: OpenRouter
    file: openrouter
    model_id: reflection/beam-1.0-501b-a23b:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-10-28"
  - name: Kilo Code
    file: kilo-code
    model_id: reflection/beam-1.0-501b-a23b:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-10-28"
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

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `beam-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |
| [OpenRouter](../providers/openrouter.md) | `reflection/beam-1.0-501b-a23b:free` | Permanent `:free` variant; account + key, no card | Provider-wide free-model caps apply; roster rotates | 2026-10-28 |
| [Kilo Code](../providers/kilo-code.md) | `reflection/beam-1.0-501b-a23b:free` | Standing `:free` lane; anonymous keyless access allowed | Provider-wide anonymous `:free` quota applies | 2026-10-28 |

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