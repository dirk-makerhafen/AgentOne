---
name: OpenRouter
url: https://openrouter.ai
api_base: https://openrouter.ai/api/v1
litellm_prefix: openrouter
setup_instructions: '1. Create an account at https://openrouter.ai (email signup;
  no credit card required for free models).

  2. Create an API key at https://openrouter.ai/keys.

  3. Optional: purchase at least $10 in credits at https://openrouter.ai/settings/credits
  to raise the free-model allowance from 50 to 1,000 requests/day.

  4. POST to https://openrouter.ai/api/v1/chat/completions with {"model": "<slug>:free",
  ...} and "Authorization: Bearer <key>".

  5. Check quota/credit status anytime via GET https://openrouter.ai/api/v1/key.

  '
api_key_url: https://openrouter.ai/keys
---

OpenRouter exposes free (`:free`-suffixed) variants of models through its unified OpenAI-compatible API, with low rate limits that rise after $10 in lifetime credit purchases.

**Sources**

- https://openrouter.ai/docs/api_reference/limits (20 RPM, 50/1,000 per day, $10 threshold verified 2026-09-05)
- https://openrouter.ai/docs/faq (free-tier terms, privacy, fees verified 2026-09-05)
- https://openrouter.ai/docs/guides/routing/model-variants/free
- https://openrouter.ai/api/v1/models (live `:free` roster enumerated 2026-09-05)
- https://openrouter.ai/docs (quickstart)
