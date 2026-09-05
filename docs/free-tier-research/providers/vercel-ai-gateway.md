---
name: Vercel AI Gateway
url: "https://vercel.com"
setup_instructions: |
  1. Create a Vercel team account and open the AI Gateway section of the dashboard.
  2. Create an AI Gateway API key (AI_GATEWAY_API_KEY).
  3. Free credits start on the first AI Gateway request; pick a model from the Free Tier catalog (?freeTier=true).
api_key_url: "https://vercel.com"
limits: {}
---

Vercel AI Gateway (zero-markup, zero-fee token passthrough) gives every team a monthly free-credit tier covering a subset of models at lower per-model rate limits.

**Free Tier:**

- Monthly free credit (not a one-time trial), covering a subset of the catalog — browse with the `?freeTier=true` filter.
- Free-tier requests are rate-limited per model below paid-tier limits; over-limit returns 429.
- Purchasing AI Gateway Credits moves the team to the paid tier and ends the monthly free credit.

**Free Models:**

- Rotating subset (observed: `meta/llama-4-maverick`, `meta/llama-4-scout`, `meta/llama-3.3-70b`) — resolve live in the dashboard, not hardcoded here.

**Limits:**

- Published numerics: none fixed (per-model, paid tier higher); 429 + retry-after semantics documented on the rate-limits page.

**Notes:**

- Vercel account required; API key required; no payment for the free tier.
- BYOK is paid-tier-only and needs purchased credits.
- No markup or platform fee on tokens on any tier; payment-processing fees may apply to top-ups.

**Sources**

- https://vercel.com/docs/ai-gateway/pricing (free-tier terms verified 2026-09-05)
- https://vercel.com/docs/ai-gateway/faq
- https://vercel.com/docs/ai-gateway/rate-limits
