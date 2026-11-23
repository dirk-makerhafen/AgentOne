---
name: Poolside
url: https://poolside.ai
api_base: https://inference.poolside.ai/v1
setup_instructions: '1. Sign in to https://platform.poolside.ai, open the API Keys
  tab, and click New key.

  2. Point an OpenAI-compatible client at base URL https://inference.poolside.ai/v1
  with the key as a Bearer token.

  3. Call with model `poolside/laguna-s-2.1` or `poolside/laguna-xs-2.1`.

  '
api_key_url: https://platform.poolside.ai
---

Poolside trains its own Laguna coding models and serves them via an OpenAI-compatible API that is "free to use for a limited time" (time-boxed promo, still current with no end date published as of 2026-09-05).

**Sources**

- https://poolside.ai/models ("Free to use for a limited time", model IDs, weights links — verified 2026-09-05)
- https://docs.poolside.ai/api/overview (base URL, endpoints, key steps)
- https://docs.poolside.ai/get-started/supported-models (parameters, context windows, licenses)
- https://openrouter.ai/poolside/laguna-s-2.1:free (third-party free-row training-data notice)
