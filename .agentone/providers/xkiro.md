---
name: xKiro
url: https://xkiro.com
api_base: https://api.xkiro.com/v1
setup_instructions: '1. Sign up at https://xkiro.com/dashboard (no credit card) and
  create an API key (`sk-xt-...`).

  2. Call https://api.xkiro.com/v1/chat/completions with `Authorization: Bearer <key>`
  (or `x-api-key`).

  3. GET /v1/models is public; filter rows where `access_tier: free` and keep the
  `vendor/` prefix in model ids.

  4. Optional: verify Telegram in the dashboard to double the daily free-token allowance.

  '
api_key_url: https://xkiro.com/dashboard
---

xKiro is an OpenAI-compatible (plus Anthropic Messages) gateway with a documented permanent Free plan: 26 free models available to every account, 500,000 free tokens/day, no card. Verified 2026-11-20.

**Sources**

- https://xkiro.com/
- https://docs.xkiro.com/api/overview/
- https://docs.xkiro.com/api/usage/
- https://docs.xkiro.com/api/rate-limits/
- https://docs.xkiro.com/models/
- https://docs.xkiro.com/models/tiers/
- https://api.xkiro.com/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/xkiro.json (discovery lead, verified 2026-11-20)
