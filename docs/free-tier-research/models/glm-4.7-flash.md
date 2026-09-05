---
name: GLM-4.7-Flash
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-4.7-flash
family: glm-flash
context_window: 200000
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
    model_id: glm-4.7-flash
    conditions: "Permanent zero-price (in, cache, out all Free); account + key, no card; official numeric limits unpublished, account- and model-specific rate-limit view"
    verified: "2026-09-05"
---

GLM-4.7-Flash is Z.AI's efficient reasoning/coding model with a permanent zero-price API tier (context ≈200K per secondary data; verify live).

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text in / text out; ~200K context (secondary data, verify live).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Z.AI](../providers/z-ai.md) | `glm-4.7-flash` | Permanent zero-price (in, cache, out all Free); account + key, no card | Official numeric limits unpublished; account- and model-specific rate-limit view | 2026-09-05 |

**Notes:**

- Do not confuse with `glm-4.7-flashx` (paid FlashX lane) or the GLM Coding Plan subscription (separate product/endpoints, from $18/mo).
- KUAE Cloud's $0 GLM-4.7 row is a 30-day trial, not a standing tier — excluded.
- ZenMux `$0` GLM-4.7-Flash rows require a paid plan for any API access — excluded.

**Sources**

- https://docs.z.ai/guides/overview/pricing
- https://docs.z.ai/devpack/overview (coding-plan separation)
