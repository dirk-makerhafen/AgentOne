---
name: Vercel AI Gateway
url: https://vercel.com
api_base: https://ai-gateway.vercel.sh/v1
setup_instructions: '1. Create a Vercel account and a team, and add a valid payment
  method to the team (required to unlock the free credits; no purchase required).

  2. Open the AI Gateway API-keys section of the dashboard and create an API key;
  export it as AI_GATEWAY_API_KEY.

  3. Free credits start on the first AI Gateway request; call an OpenAI-compatible
  client at https://ai-gateway.vercel.sh/v1 with a model from the Free Tier catalog
  (?freeTier=true) — other models return 403 until credits are purchased.

  '
api_key_url: https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai-gateway%2Fapi-keys
---

Vercel AI Gateway (zero-markup token passthrough) gives every team a recurring monthly free-credit tier covering a subset of models at lower per-model rate limits.

**Sources**

- https://vercel.com/docs/ai-gateway/pricing ($5/month free credit, verified 2026-09-05; page last updated 2026-09-02)
- https://vercel.com/docs/ai-gateway/getting-started (payment-method requirement, key steps, endpoint, 403 behavior)
- https://vercel.com/docs/ai-gateway/rate-limits (free vs paid tiers, 429 semantics)
- https://vercel.com/docs/ai-gateway/faq (monthly credit, not a trial)
