---
name: IO Intelligence
url: https://io.net
api_base: https://api.intelligence.io.solutions/api/v1
setup_instructions: '1. Sign up for an io.net account (starts on the free Standard
  plan by default).

  2. Create an API key in the dashboard under API Keys (set a name, project "IO Intelligence",
  permissions, and an expiry of 30/60/90/180 days).

  3. Call the OpenAI-compatible API at https://api.intelligence.io.solutions/api/v1
  with the key as Bearer token.

  4. Resolve current model IDs and per-model credit burn rates live via GET /models
  (input_token_price / output_token_price fields).

  '
api_key_url: https://ai.io.net/ai/api-keys
---

IO Intelligence (io.net's inference product) puts new accounts on a free Standard plan by default: light daily access from an auto-refreshing shared credit pool, with pay-as-you-go via IO Credits once the daily allowance is exceeded.

**Sources**

- https://io.net/docs/guides/payment/io-intelligence-payments (free Standard plan + shared pool, verified 2026-09-05)
- https://io.net/docs/reference/ai-models/get-started-with-io-intelligence-api (endpoint, key creation at ai.io.net/ai/api-keys, verified 2026-09-05)
- https://io.net/docs/guides/intelligence/io-intelligence-apis (key creation steps, endpoint, verified 2026-09-05)
