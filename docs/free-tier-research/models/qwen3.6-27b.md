---
name: Qwen3.6-27B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3.6-27b
leaderboard_id: qwen3.6-27b
leaderboard_rank: 64
family: qwen3
context_window: 262144
reasoning: true
tool_call: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: Groq
    file: groq
    model_id: qwen/qwen3.6-27b
    conditions: "Free plan; account + key, no card for Free tier"
    limits:
      requests:
        minute: 30
        day: 1000
      tokens:
        minute: 8000
        day: 200000
    verified: "2026-09-05"
  - name: InferX
    file: inferx
    model_id: Qwen3.6-27B-FP8
    conditions: "InferX Free $0/mo promo ('Free · 100% off'); account + key; promos rotate, re-verify pricing page"
    verified: "2026-09-05"
---

Qwen3.6-27B is Alibaba Qwen team's April 2026 dense flagship ("flagship-level coding in a 27B dense model", beating the 397B Qwen3.5 MoE on coding benchmarks): a 27B-parameter dense open-weight model with thinking/non-thinking modes and tool calling. Its 35B-A3B MoE sibling has its own [card](qwen3.6-35b-a3b.md). Qwen3.8 (August 2026) is a separate, newer generation with its own [card](qwen3.8.md).

**Capabilities:**

- Reasoning (thinking/non-thinking modes, `reasoning_effort` control), tool/function calling (official model card, Groq docs).
- Text + image in / text out (vision encoder shared with the 3.8 generation; Groq documents multimodal input).
- Open weights under Apache 2.0 (Hugging Face `Qwen/Qwen3.6-27B`).
- 262,144 native context, extendable toward ~1M via YaRN.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Groq](../providers/groq.md) | `qwen/qwen3.6-27b` | Free plan; account + key, no card for Free tier | 30 RPM / 1,000 RPD / 8K TPM / 200K TPD (official Free Plan) | 2026-09-05 |
| [InferX](../providers/inferx.md) | `Qwen3.6-27B-FP8` | InferX Free $0/mo promo; account + key | No published numbers; promos rotate | 2026-09-05 |

**Notes:**

- Sibling size: [`Qwen3.6-35B-A3B`](qwen3.6-35b-a3b.md) (35B total / 3B active MoE, served as FP8 rows on InferX/Hetzner).
- Qwen3.6 (April 2026) and Qwen3.8 (August 2026, "most capable generation in the Qwen open-model family to date") are distinct generations sharing an architectural foundation — see [qwen3.8.md](qwen3.8.md) for the newer generation.
- Model Studio hosted `qwen3.6-27b` config (131072 context / 16384 max tokens) is a hosted-deployment cap, not the weights' native spec — not used as card default.
- Do not confuse with `Qwen3-32B` ([card](qwen3-32b.md)) or `Qwen3.5-397B-A17B` ([card](qwen3.5-397b.md)).

**Sources**

- https://huggingface.co/Qwen/Qwen3.6-27B (262,144 native, tool calling, thinking modes)
- https://qwen.ai/blog?id=qwen3.6-27b (April 2026 release, vs Qwen3.5-397B)
- https://console.groq.com/docs/rate-limits (Free Plan figures)
- https://inferx.net/pricing/endpoints
