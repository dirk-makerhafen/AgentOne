---
name: GLM-5.3-Flash
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-5.3-flash
family: glm
leaderboard_id: glm-5.3-flash
leaderboard_rank: 22
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
    model_id: glm-5.3-flash:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
---

GLM-5.3-Flash is Zhipu AI (Z.AI)'s efficient open-weight coding/agent MoE variant (320B total / 18B active), sharing GLM-5.3's post-training stack. Sibling cards: [GLM-5.3](glm-5.3.md), [GLM-5.2](glm-5.2.md). See also [GLM-4.7-Flash](glm-4.7-flash.md).

**Capabilities:**

- Reasoning with effort control, function/tool calling, structured output, temperature control (same post-training stack as 5.3; Flash-specific context/output figures unverified — omitted).
- Text in / text out.
- Open weights (Hugging Face `zai-org/GLM-5.3-Flash`; FP8 + BF16).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `glm-5.3-flash:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |

**Notes:**

- Context window / max output tokens omitted: no Flash-specific official figures verified; 5.3's 1M/128K numbers are not inherited here.
- Excluded (not free): LLM7.io lists `glm-5.3-flash` as `pro`-tier, not `turbo` — not reachable on free tiers.
- Excluded (unverifiable subset): Ollama Cloud lists `glm-5.3-flash` at pay-per-token rates with an unlabeled starter-model subset — not claimed as a free row.
- Do not confuse with `glm-4.7-flash` ([card](glm-4.7-flash.md)) or the GLM Coding Plan subscription (separate product/endpoints).

**Sources**

- https://github.com/zai-org/GLM-5 (320B-A18B size, open weights, reasoning_effort levels)
- https://z.ai/blog/glm-5.3 (post-training lineage)
- https://unorouter.com/en/models
- https://ollama.com/pricing
