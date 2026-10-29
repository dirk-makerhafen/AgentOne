---
name: Jev 1.13 Free
developer: TypeSafe AI
canonical_id: typesafe/jev-1.13
leaderboard_id: jev-1.13-free
leaderboard_rank: 88
family: jev
context_window: 262144
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: false
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: jev-1.13-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
---

Jev 1.13 is TypeSafe AI's first "System One Model" — a new class of frontier models built for fast, structured decisions that software can use directly. Unlike traditional LLMs, Jev gives up string generation in favor of type-safe structured outputs with calibrated probabilities. It achieves frontier-level intelligence on System One tasks while being ~100-200x faster and dramatically cheaper.

**Capabilities:**

- **System One interface**: Unstructured state in, typed probabilistic decisions out (not free-form text)
- **No hallucination / type errors**: Schema matching is mathematically guaranteed; the model never makes type errors
- **Calibrated confidence**: Every output includes epistemically honest probabilities — higher confidence means higher accuracy
- **Parallel sampling**: Generates all outputs in a single query (70ms-500ms end-to-end) vs. sequential token generation
- **Tool/function calling**: Native structured decision outputs that slot into code as "smart if-statements"
- **Reasoning**: Internal reasoning with configurable effort (low, medium, high, xhigh, max)
- **Temperature control**
- **Text in / structured decisions out** (represented as text for API compatibility)
- 262K context window, 65K max output
- Proprietary weights (not open)
- Knowledge cutoff: 2026-06 (per models.dev)

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `jev-1.13-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |

**Notes:**

- Release date: 2026-10-20 (per opencode fixture)
- Canonical model: `typesafe/jev-1.13`
- **Fundamentally different from LLMs**: Does not generate strings; outputs typed structured decisions with calibrated probabilities
- Pricing (paid): Input $0.042/MTok, Output FREE ("too cheap to meter")
- On OpenRouter as `typesafe/jev-1.13` (paid, not free)
- On OpenCode Zen as `jev-1.13-free` (anonymous, no key, limited-time free pool)
- Use cases: AI-powered workflows, classification, routing, scoring, extraction, map-reduce over big data, real-time applications, verification/guardrails
- Data handling: TypeSafe states they make all training data themselves and wouldn't train on user data even if asked

**Sources**

- https://typesafe.ai/blog/introducing-system-one-models-and-jev (official announcement, 2026-09-15)
- https://openrouter.ai/typesafe/jev-1.13 (OpenRouter listing)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)
- https://docs.typesafe.ai/models (TypeSafe model docs)