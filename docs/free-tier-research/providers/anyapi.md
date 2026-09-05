---
name: AnyAPI
url: "https://anyapi.ai"
setup_instructions: |
  1. Create an account at https://dash.anyapi.ai/ (no credit card required for the Free plan).
  2. Create an API key in the dashboard.
  3. Call the API at https://api.anyapi.ai/v1 with the key and a free or basic model ID.
api_key_url: "https://dash.anyapi.ai/"
limits:
  tokens:
    day: 100000
---

AnyAPI is a unified gateway over 400+ models with a standing Free ($0/mo) plan: 100K ANY Tokens/day across all free and basic models, no credit card required.

**Free Tier:**

- Standing Free plan, not a trial: $0/mo, 100K ANY Tokens/day, unlimited users, community support.
- No credit card required. "Limited API calls" noted on the plan.

**Free Models:**

- All free and basic models (see https://anyapi.ai/ai-models for the live list, which marks per-model ANY-token costs; some rows show $0/0, e.g. `google-gemma-3n-4b-free`, `liquidai-lfm2-5-1-2b-instruct-free`, `google-gemini-2-5-pro-preview-05-06` — verify live before use).
- Paid models (400+ catalog) require Pay-as-you-go (from $20 usage-based) or a monthly plan.

**Limits:**

- 100K ANY Tokens/day on the Free plan (provider token unit; maps to model token costs on the models page).
- Request-rate (RPM/RPD) figures: unknown — not published on the pricing page.

**Notes:**

- Account required; API key required; no payment for the Free plan.
- Extras on Free: AnyAPI SDK, AnyCLI, AnyChat access.

**Sources**

- https://anyapi.ai/pricing (Free plan terms verified 2026-09-05)
- https://docs.anyapi.ai
