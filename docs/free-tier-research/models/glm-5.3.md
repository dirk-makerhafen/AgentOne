---
name: GLM-5.3
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-5.3
family: glm
leaderboard_id: glm-5.3
context_window: 1000000
max_output_tokens: 131072
reasoning: true
tool_call: true
temperature: true
structured_output: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: UnoRouter
    file: unorouter
    model_id: glm-5.3:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: PrivateMode
    file: privatemode-ai
    model_id: GLM-5.3
    conditions: "Free tier 1M prompt + 1M completion tokens/mo (multiplier 1.0); account + org + key, no card"
    verified: "2026-09-05"
---

GLM-5.3 is Zhipu AI (Z.AI)'s flagship open-weight long-horizon coding/agent MoE model (744B total / 40B active). It uses the same base model as GLM-5.2 with all gains from post-training. Sibling cards: [GLM-5.3-Flash](glm-5.3-flash.md), [GLM-5.2](glm-5.2.md).

**Capabilities:**

- Always-on reasoning with effort control (`low`/`high`/`max`), function/tool calling, structured output, temperature control (official docs).
- Text in / text out (official: text-only inputs); 1M context, 128K max output (official figures).
- Open weights (Hugging Face `zai-org/GLM-5.3`; FP8 + BF16).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `glm-5.3:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [PrivateMode](../providers/privatemode-ai.md) | `GLM-5.3` | Free tier 1M prompt + 1M completion tokens/mo (multiplier 1.0); account + org + key, no card | None published combo-specific (baseline quota); plus one-time 5M-token new-org grant | 2026-09-05 |

**Notes:**

- Excluded (not free): LLM7.io lists `glm-5.3` as `pro`-tier, not `turbo` — not reachable on free tiers.
- Excluded (unverifiable subset): Ollama Cloud lists `glm-5.3` at pay-per-token rates with an unlabeled starter-model subset — not claimed as a free row.
- Excluded (unmappable): StreamLake Vanchin lists `GLM-5.3` base models, but the provider-side ID is always a per-user endpoint ID and per-model free eligibility is login-gated — no 1:1 card row assertable.
- PrivateMode's pricing table still lists `GLM-5.2` while its rate-limits page lists `GLM-5.3` — confirm the live model ID before use; only `GLM-5.3` is claimed here.
- Do not confuse with `glm-4.7-flash` ([card](glm-4.7-flash.md)) or the GLM Coding Plan subscription (separate product/endpoints).

**Sources**

- https://docs.z.ai/guides/llm/glm-5.3 (1M context, 128K max output, text-only, always-on reasoning, function calling, structured output)
- https://github.com/zai-org/GLM-5 (744B-A40B size, open weights, reasoning_effort levels)
- https://z.ai/blog/glm-5.3 (post-training lineage)
- https://unorouter.com/en/models
- https://docs.privatemode.ai/rate-limits/
- https://ollama.com/pricing
