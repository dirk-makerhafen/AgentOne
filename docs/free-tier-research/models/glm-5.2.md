---
name: GLM-5.2
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-5.2
family: glm
leaderboard_id: glm-5.2
leaderboard_rank: 34
context_window: 1000000
reasoning: true
tool_call: true
temperature: true
structured_output: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: OpenRouter
    file: openrouter
    model_id: z-ai/glm-5.2:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    limits:
      requests:
        minute: 20
        day: 50
    verified: "2026-09-05"
---

GLM-5.2 is Zhipu AI (Z.AI)'s open-weight long-horizon coding/agent MoE model (744B total / 40B active) — the same base model as GLM-5.3, before 5.3's post-training gains. Sibling cards: [GLM-5.3](glm-5.3.md), [GLM-5.3-Flash](glm-5.3-flash.md).

**Capabilities:**

- Reasoning (`high`/`max`), function/tool calling, structured output, temperature control (official docs).
- Text in / text out; 1M context (official docs; max-output figure unverified — omitted).
- Open weights (Hugging Face `zai-org/GLM-5.2`; FP8 + BF16).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenRouter](../providers/openrouter.md) | `z-ai/glm-5.2:free` | Permanent `:free` variant; account + key, no card | 20 req/min; 50 req/day baseline (1,000/day after $10 lifetime credits); roster rotates | 2026-09-05 |

**Notes:**

- PrivateMode's pricing table still lists `GLM-5.2` while its rate-limits page lists `GLM-5.3` — confirm the live model ID before use; only the OpenRouter `:free` row is claimed here.
- Excluded (unmappable): StreamLake Vanchin lists `GLM-5.2` base models, but the provider-side ID is always a per-user endpoint ID and per-model free eligibility is login-gated — no 1:1 card row assertable.
- Do not confuse with `glm-4.7-flash` ([card](glm-4.7-flash.md)) or the GLM Coding Plan subscription (separate product/endpoints).

**Sources**

- https://docs.z.ai/guides/llm/glm-5.2 (1M context, same-base lineage)
- https://github.com/zai-org/GLM-5 (744B-A40B size, open weights, reasoning_effort levels)
- https://openrouter.ai/api/v1/models (live `:free` roster)
