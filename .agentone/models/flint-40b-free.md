---
name: Flint 40B Free
developer: Recursive AI
canonical_id: recursive/flint
leaderboard_id: flint-40b-free
leaderboard_rank: 203
family: flint
context_window: 262144
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
    model_id: flint-40b-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
---

Flint 40B is an open-weight mixture-of-experts (MoE) model with approximately 40B total parameters and ~2.5B active parameters, designed for local coding agents and efficient inference.

**Capabilities:**

- Sparse MoE architecture: ~40B total / ~2.5B active parameters for efficient inference
- Reasoning with configurable effort levels (low, medium, high, xhigh, max)
- Tool/function calling support
- Structured output support
- Temperature control
- Text in / text out
- 262K context window
- Open weights (Recursive AI release)

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `flint-40b-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |

**Notes:**

- Knowledge cutoff: 2026-06
- Release date: 2026-10-21
- Canonical model: `recursive/flint`
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Designed for local deployment and coding agents

**Sources**

- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)