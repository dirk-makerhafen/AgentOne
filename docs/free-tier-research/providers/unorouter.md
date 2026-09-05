---
name: UnoRouter
url: "https://unorouter.com"
setup_instructions: |
  1. Sign up at https://unorouter.com with Discord or GitHub (no credit card required for free models).
  2. Create an API key in the dashboard.
  3. Call the OpenAI-compatible API at https://api.unorouter.com/v1 with the key, using a model ID with the `:free` suffix.
api_key_url: "https://unorouter.com"
limits:
  requests:
    minute: 1
---

UnoRouter is an open-source OpenRouter alternative: one API key for 200+ models behind an OpenAI-compatible endpoint. It aggregates free lanes from ~18 upstream providers into 190+ `$0`-per-token `:free` model rows behind a single key.

**Free Tier:**

- Any model ID with the `:free` suffix costs $0 per token; no credit card required (Discord/GitHub signup + key).
- Free tier is best-effort throughput, not guaranteed: each upstream enforces its own RPM/daily quotas, and drained pools return an explicit all-providers-busy error until they recover.
- Paid models bill pay-as-you-go from a $1 top-up (credits never expire); paid subscriptions only reduce waiting between free-model requests.

**Free Models (examples observed 2026-09-05; the set shifts as pools drain/recover — resolve live at https://unorouter.com/models filtered for free):**

- [`deepseek-v4-flash:free`](../models/deepseek-v4-flash.md) / [`deepseek-v4-pro:free`](../models/deepseek-v4-pro.md) — DeepSeek.
- `glm-5.3:free` / `glm-5.3-flash:free` — Z.AI GLM, 1M context.
- [`gemma-4-31b-it:free`](../models/gemma-4-31b-it.md) — Google Gemma.
- `qwen-3.8-27b:free` — Alibaba Qwen, 262K context.
- `gemini-3.6-flash:free` — Google Gemini.
- `deepseek-reasoner:free` — DeepSeek reasoning.
- `dots-3-note-preview:free` — Dots Studio, 512K context.
- `nemotron-3.5-lightning:free` — Nvidia, 262K context.
- `agnes-2.0-flash:free`, `aion-3.0-mini:free`, `codestral-latest:free`, `command-r-plus:free` — misc free rows.

**Limits:**

- ~1 request/minute per free model per user (UnoRouter's own fairness cap); hitting it returns HTTP 429 with a `Retry-After` header. Upstream caps apply on top.
- Practical guidance from the provider: rotate across the many free models instead of hammering one.

**Notes:**

- Account required; API key required; no payment for the free tier.
- Endpoints: `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, plus Anthropic-native `/v1/messages` and Gemini-native `/v1beta`; base URL `https://api.unorouter.com/v1`.
- Entire stack is public under OSI licenses and self-hostable.
- Data/training policy for free-tier requests: unknown (not documented on pages checked).

**Sources**

- https://unorouter.com/en (free-tier terms, 1 req/min, no card verified 2026-09-05)
- https://unorouter.com/en/blog/free-models-aggregated (190+ free rows, 18 upstream providers)
- https://unorouter.com/en/pricing
- https://unorouter.com/en/docs/platform
- https://unorouter.com/en/models
