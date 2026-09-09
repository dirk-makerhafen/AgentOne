---
name: Vercel AI Gateway
url: "https://vercel.com"
api_base: "https://ai-gateway.vercel.sh/v1"
setup_instructions: |
  1. Create a Vercel account and a team, and add a valid payment method to the team (required to unlock the free credits; no purchase required).
  2. Open the AI Gateway API-keys section of the dashboard and create an API key; export it as AI_GATEWAY_API_KEY.
  3. Free credits start on the first AI Gateway request; call an OpenAI-compatible client at https://ai-gateway.vercel.sh/v1 with a model from the Free Tier catalog (?freeTier=true) — other models return 403 until credits are purchased.
api_key_url: "https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai-gateway%2Fapi-keys"
limits: {}
---

Vercel AI Gateway (zero-markup token passthrough) gives every team a recurring monthly free-credit tier covering a subset of models at lower per-model rate limits.

**Free Tier:**

- Monthly free credit of **$5/month, recurring** (not a one-time trial) — still current per pricing docs last updated 2026-09-02. Credits start on the first AI Gateway request.
- Covers a subset of the catalog only — browse with the `?freeTier=true` filter or `GET /v1/models`. Calling any other model without purchased credits returns 403.
- Free-tier requests are rate-limited per model below paid-tier limits; over-limit returns 429 (honor `retry-after`, retry with backoff).
- Purchasing AI Gateway Credits moves the team to the paid tier permanently and ends the monthly free credit.

**Free Models:**

- Rotating free-tier-eligible subset — resolve live in the dashboard (`/ai-gateway/models?freeTier=true`) or via `GET /v1/models`, not hardcoded here. (No fixed model list is documented; per-model free eligibility changes.)

**Limits:**

- Published numerics: $5/month included credit (documented; kept in body because the frontmatter schema covers only requests/tokens-over-time). No fixed RPM/RPD/TPM numbers are documented — Vercel describes behavior, not numbers.

**Notes:**

- Vercel account required; API key required; a valid payment method on the team is required to unlock the free credits (without one the API returns 403 `customer_verification_required`) — no credit purchase required for the free tier.
- Endpoint: `https://ai-gateway.vercel.sh/v1` (OpenAI Chat Completions/Responses; e.g. `POST https://ai-gateway.vercel.sh/v1/chat/completions`), model IDs in `provider/model` format used exactly as the catalog returns them.
- BYOK requests use the provider's own rate limits; fallback to gateway credentials is billed to AI Gateway Credits.
- No markup or platform fee on tokens on any tier; payment-processing fees may apply to top-ups. Team-wide zero-data-retention and allowlists are paid extras.

**Sources**

- https://vercel.com/docs/ai-gateway/pricing ($5/month free credit, verified 2026-09-05; page last updated 2026-09-02)
- https://vercel.com/docs/ai-gateway/getting-started (payment-method requirement, key steps, endpoint, 403 behavior)
- https://vercel.com/docs/ai-gateway/rate-limits (free vs paid tiers, 429 semantics)
- https://vercel.com/docs/ai-gateway/faq (monthly credit, not a trial)
