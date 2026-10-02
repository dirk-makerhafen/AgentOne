---
name: Z.AI
url: "https://z.ai/"
api_base: "https://api.z.ai/api/paas/v4"
setup_instructions: |
  1. Register or log in at https://z.ai/model-api.
  2. Create an API key at https://z.ai/manage-apikey/apikey-list and copy it.
  3. Call the OpenAI-compatible endpoint https://api.z.ai/api/paas/v4/chat/completions with header `Authorization: Bearer YOUR_API_KEY` and a free model ID.
api_key_url: "https://z.ai/manage-apikey/apikey-list"
limits: {}
---

Z.AI (Zhipu AI) API offers three permanently zero-priced GLM Flash models alongside paid models, via an OpenAI-compatible endpoint (verified 2026-09-05).

**Free Tier:**

- Permanent zero-priced models (input, cached input, and output all listed as Free on the official pricing page), not trial credits.
- No credit card stated as required for the free models (discovery trackers report "no card"); paid models are billed per token.

**Free Models:**

- [glm-4.7-flash](../models/glm-4.7-flash.md) — text/reasoning; described in official release notes (2026-01-19) as the free-tier version of GLM-4.7. (Context per discovery data: 200K; verify live.)
- `glm-4.5-flash` — text/reasoning; ≥1yr-old superseded generation, deliberately not catalogued as a model card (see README "Filenames" rule). Still permanently $0 here (in/cache/out all Free); context per discovery data 128K, verify live.
- `glm-4.6v-flash` — vision/multimodal. (Context per discovery data: 128K; verify live.)

**Limits:**

- Official numeric free-tier rate limits are unpublished; the rate-limit view is account- and model-specific (see https://z.ai/manage-apikey/rate-limits and https://docs.z.ai/api-reference/rate-limit).
- Secondary tracker reports only (unverified, not contractual): ~1 concurrent request, ~60 req/min, ~1,000 req/day.
- Cached-input storage is "Limited-time Free" (promo; read discount still billed on paid models).

**Notes:**

- Account required; API key required (Bearer or JWT).
- Phone verification: unknown.
- Payment/billing info: not required for free models (no card stated); required to use paid models.
- Base URLs: international `https://api.z.ai/api/paas/v4/`; China-domestic `https://open.bigmodel.cn/api/paas/v4`.
- Infrastructure primarily in China (latency/data-residency consideration).
- GLM Coding Plan is a separate subscription product with dedicated endpoints; its quota does not pay for General API calls.
- Data usage/training policy: unknown.
- Paid reference points (official pricing page, verified 2026-09-05): GLM-5.3 $1.40/$4.40 per 1M in/out; GLM-5.3-Flash $0.075/$0.25 (promo ends 24:00 Sept 9 2026 UTC+8); GLM-4.7-FlashX $0.07/$0.40.

**Sources**

- https://docs.z.ai/guides/overview/pricing (Free rows, paid prices verified 2026-09-05)
- https://docs.z.ai/guides/develop/http/introduction (signup, key, endpoint verified 2026-09-05)
- https://docs.z.ai/release-notes/new-released (GLM-4.7-Flash free-tier positioning verified 2026-09-05)
- https://z.ai/manage-apikey/rate-limits (account-specific limits view)
- https://docs.z.ai/api-reference/rate-limit
- https://www.layer3labs.io/guides/z-ai-pricing (secondary, 2026-08-29)
