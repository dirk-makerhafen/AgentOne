---
name: GLM-4.5-Flash
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-4.5-flash
family: glm-flash
context_window: 131072
max_output_tokens: 98304
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
knowledge_cutoff: "2025-04"
providers:
  - name: Z.AI
    file: z-ai
    model_id: glm-4.5-flash
    conditions: "Permanent zero-price (in, cache, out all Free); account + key, no card; official numeric limits unpublished, account- and model-specific rate-limit view"
    verified: "2026-09-05"
  - name: UnoRouter
    file: unorouter
    model_id: glm-4.5-flash:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
---

GLM-4.5-Flash is Z.AI's efficient reasoning/coding model with a permanent zero-price API tier (fixture-reported capabilities; verify live).

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text in / text out; ~128K context (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Z.AI](../providers/z-ai.md) | `glm-4.5-flash` | Permanent zero-price (in, cache, out all Free); account + key, no card | Official numeric limits unpublished; account- and model-specific rate-limit view | 2026-09-05 |
| [UnoRouter](../providers/unorouter.md) | `glm-4.5-flash:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |

**Sources**

- https://docs.z.ai/guides/overview/pricing
- raw/opencode-models-api/zai/model_glm-4.5-flash.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
