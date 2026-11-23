---
name: ZenMux
url: https://zenmux.ai
api_base: https://zenmux.ai/api/v1
setup_instructions: '1. Sign in at https://zenmux.ai/login (email, GitHub, or Google;
  no payment information required for the free lane).

  2. Create an API key in the ZenMux console (Pay As You Go management page / platform
  management).

  3. POST to https://zenmux.ai/api/v1/chat/completions (OpenAI-compatible) with {"model":
  "<provider>/<slug>", ...} and "Authorization: Bearer <key>". Anthropic protocol
  at /api/anthropic, Gemini protocol at /api/vertex-ai.

  4. Free-lane models are billed $0 per token, marked "Free" with a "Rate Limit" badge
  on the model page, and are usable without a prepaid balance; only paid models require
  a PAYG top-up or the Builder subscription.

  '
api_key_url: https://zenmux.ai/platform/pay-as-you-go
---

ZenMux is a model aggregation router (OpenAI/Anthropic/Gemini-compatible) that runs a "Free" lane: a rotating set of models billed at $0/M tokens, rate-limited, available after a simple sign-in plus API key with no payment information.

**Sources**

- https://zenmux.ai/models (live free roster, filters, model detail pages verified 2026-09-06)
- https://zenmux.ai/docs/guide/quickstart.html (sign-in, API key, plans, base URLs)
- https://zenmux.ai/z-ai/glm-4.7-flash-free ($0 free lane, rate-limit badge, 200K context)
- https://zenmux.blog/blog (official blog "4 Truly Free LLM APIs" — free lane terms; rate-limited)
- https://zenmux.ai/pricing/overview
