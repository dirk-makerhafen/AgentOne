---
name: EmpirioLabs
url: "https://empiriolabs.ai"
setup_instructions: |
  1. Sign up at https://empiriolabs.ai/get-started (creates your account on https://platform.empiriolabs.ai; pay-as-you-go starts at $0).
  2. Generate an API key from the dashboard (keys use the `sk-empiriolabs-` prefix) and export it as EMPIRIOLABS_API_KEY.
  3. Point an OpenAI-compatible client at base URL https://api.empiriolabs.ai/v1 and call with a model marked Free on the pricing page.
api_key_url: "https://platform.empiriolabs.ai"
limits: {}
---

EmpirioLabs is a model gateway with an OpenAI-compatible API whose pay-as-you-go plan starts at $0; models badged "Free" on the pricing page cost nothing and never draw from allowances or credit balance.

**Free Tier:**

- Pay-as-you-go with $0 to start ("Start for free"); free models run at no cost.
- Paid plans (Lite $19.90/mo, Pro $49.90/mo, Max $199.90/mo) add weekly token/media allowances on top; usage inside allowances never touches the credit balance, and anything beyond bills at normal pay-as-you-go rates.
- Allowances are for personal use only (no reselling), refresh weekly, and do not roll over.

**Free Models (exactly the 3 models badged "Free" on the official pricing page, verified 2026-09-05):**

- [`glm-4-7-flash`](../models/glm-4.7-flash.md) (`glm-4-7-flash`) — Z.ai GLM flash model, input/output per 1M tokens Free.
- `glm-4-6v-flash` (`glm-4-6v-flash`) — Z.ai GLM vision flash model, input/output per 1M tokens Free.
- [`glm-4-5-flash`](../models/glm-4.5-flash.md) (`glm-4-5-flash`) — Z.ai GLM flash model, input/output per 1M tokens Free.
- The free roster rotates (the page notes "3 of these are free to run"); the pricing page badges are the source of truth — resolve live via `GET /v1/models` or https://empiriolabs.ai/pricing, not hardcoded here.

**Limits:**

- Published numerics for the free models: none found; weekly-allowance pools apply to paid/subscription usage only.

**Notes:**

- Account required; API key required. The docs list prepaid credits as a getting-started prerequisite while the pricing page says $0 to start with free models at no cost — whether a paid top-up is enforced before a free-model-only call is unverified; confirm live.
- Endpoint `https://api.empiriolabs.ai/v1` confirmed in official docs (base URL `https://api.empiriolabs.ai`, all endpoints under `/v1/`); supports `/chat/completions` and `/responses`.
- Everything else in the catalog is paid (e.g. MiniMax M3 from $0.30/$1.20 per 1M, DeepSeek V4 Flash 0731 $0.424/$1.272 per 1M) — only the 3 badged models are free.

**Sources**

- https://empiriolabs.ai/pricing (free-model badges verified 2026-09-05)
- https://docs.empiriolabs.ai/getting-started (endpoint, signup, key prefix)
- https://docs.empiriolabs.ai/models-pricing (catalog, pricing units)
- https://empiriolabs.ai/blog/subscription-plans-lite-pro-max (plan/allowance semantics)
