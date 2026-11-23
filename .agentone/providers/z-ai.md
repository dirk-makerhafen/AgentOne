---
name: Z.AI
url: https://z.ai/
api_base: https://api.z.ai/api/paas/v4
setup_instructions: '1. Register or log in at https://z.ai/model-api.

  2. Create an API key at https://z.ai/manage-apikey/apikey-list and copy it.

  3. Call the OpenAI-compatible endpoint https://api.z.ai/api/paas/v4/chat/completions
  with header `Authorization: Bearer YOUR_API_KEY` and a free model ID.

  '
api_key_url: https://z.ai/manage-apikey/apikey-list
---

Z.AI (Zhipu AI) API offers three permanently zero-priced GLM Flash models alongside paid models, via an OpenAI-compatible endpoint (verified 2026-09-05).

**Sources**

- https://docs.z.ai/guides/overview/pricing (Free rows, paid prices verified 2026-09-05)
- https://docs.z.ai/guides/develop/http/introduction (signup, key, endpoint verified 2026-09-05)
- https://docs.z.ai/release-notes/new-released (GLM-4.7-Flash free-tier positioning verified 2026-09-05)
- https://z.ai/manage-apikey/rate-limits (account-specific limits view)
- https://docs.z.ai/api-reference/rate-limit
- https://www.layer3labs.io/guides/z-ai-pricing (secondary, 2026-08-29)
