---
name: EmpirioLabs
url: "https://empiriolabs.ai"
setup_instructions: |
  1. Create an account at https://platform.empiriolabs.ai (Pay-as-you-go starts at $0, "Start for free").
  2. Create an API key (EMPIRIOLABS_API_KEY).
  3. Call the API at https://api.empiriolabs.ai/v1 with a model marked Free on the pricing page.
api_key_url: "https://platform.empiriolabs.ai"
limits: {}
---

EmpirioLabs is a model gateway whose pay-as-you-go plan starts at $0 and whose pricing page marks selected models "Free … never draws from your weekly allowance".

**Free Tier:**

- Pay-as-you-go with $0 to start; free models cost nothing and never touch allowances or credit balance.
- Paid plans (Lite $19.90/mo and up) add weekly token/media allowances on top.

**Free Models (marked "Free" on the official pricing page, verify live):**

- [`glm-4-7-flash`](../models/glm-4.7-flash.md), `glm-4-6v-flash`, [`glm-4-5-flash`](../models/glm-4.5-flash.md) — Z.ai GLM flash models, free to run.
- Free roster rotates; the pricing page's "3 of these are free to run" note and model badges are the source of truth.

**Limits:**

- Published numerics for the free models: none found; weekly-allowance pools apply to paid/subscription usage only.

**Notes:**

- Account required; API key required; payment requirement for free-model-only use: unknown.
- Endpoint `https://api.empiriolabs.ai/v1` is fixture-reported; confirm against https://docs.empiriolabs.ai before use.

**Sources**

- https://empiriolabs.ai/pricing (free-model badges verified 2026-09-05)
- https://docs.empiriolabs.ai/models-pricing
