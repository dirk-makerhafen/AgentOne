---
name: AnyAPI
url: "https://anyapi.ai"
setup_instructions: |
  1. Create an account at https://dash.anyapi.ai/ (no credit card required for the Free plan).
  2. Create an API key in the dashboard.
  3. Call the API at https://api.anyapi.ai/v1 with the key and a free or basic model ID (model IDs are namespaced, e.g. `openai/gpt-4-turbo`).
api_key_url: "https://dash.anyapi.ai/"
limits:
  tokens:
    day: 100000
---

AnyAPI is a unified gateway over 400+ models with a standing Free ($0/mo) plan: 100K ANY Tokens/day across all free and basic models, no credit card required (verified 2026-09-05 — the 100K/day figure is still current on both the pricing page and the docs).

**Free Tier:**

- Standing Free plan, not a trial: $0/mo, 100K ANY Tokens/day, unlimited users, community support.
- No credit card required. "Limited API calls" noted on the plan.
- Free-plan users also get unlimited access to free-tier models in the Playground (Playground usage otherwise consumes credits).

**Free Models:**

- All free and basic models (see https://anyapi.ai/ai-models for the live list with per-model tier tags and ANY-token costs). Free-tier rows observed on the live catalog include `LiquidAI: LFM2.5-1.2B-Instruct (free)`, `LiquidAI: LFM2.5-1.2B-Thinking (free)`, `Google: Gemma 3n 4B (free)`, and `Qwen: Qwen2.5 Coder 32B Instruct (free)` — verify live before use, as the catalog rotates.
- Paid models (400+ catalog) require Pay-as-you-go (from $20 usage-based) or a monthly plan.

**Limits:**

- 100K ANY Tokens/day on the Free plan (provider token unit; roughly 1,000 model tokens per ANY Token for most models, more for premium models — see the models page for per-model costs).
- Request-rate (RPM/RPD) figures: unknown — not published on the pricing page.

**Notes:**

- Account required; API key required; no payment for the Free plan.
- Extras on Free: AnyAPI SDK, AnyCLI, AnyChat access.
- Fixture-reported model IDs (`deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`) are discovery leads only — their Free/Basic tier status on AnyAPI is unverified, so no model-card links are claimed here.

**Sources**

- https://anyapi.ai/pricing (Free plan: 100K ANY Tokens/day, no credit card verified 2026-09-05)
- https://docs.anyapi.ai (endpoint https://api.anyapi.ai/v1, 100K ANY Tokens/day, namespaced model IDs verified 2026-09-05)
- https://anyapi.ai/ai-models (live tier tags, free-row examples verified 2026-09-05)
