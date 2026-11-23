---
name: Kilo Code
url: https://kilo.ai
api_base: https://api.kilo.ai/api/gateway
default_api_key: public
setup_instructions: '1. No signup needed for anonymous free access — call the gateway
  directly (rate-limited per IP).

  2. Optional: sign in at https://app.kilo.ai to obtain a JWT API key (tied to your
  Kilo account) for keyed use and paid models.

  3. Point any OpenAI-compatible client at https://api.kilo.ai/api/gateway with `model`
  set to `kilo-auto/free` or a `:free` model ID.

  4. Send `Authorization: Bearer $KILO_API_KEY` when using a key; omit it for anonymous
  `:free` calls.

  '
api_key_url: https://app.kilo.ai
---

Kilo Code's Kilo Gateway is a unified OpenAI-compatible API over 500+ models with a standing free tier, including keyless anonymous access to models tagged `:free`.

**Sources**

- https://kilo.ai/docs/gateway/authentication (anonymous `:free` access, 200 req/hr/IP, JWT keys)
- https://kilo.ai/docs/getting-started/using-kilo-for-free (Auto Free router, data-handling warning)
- https://api.kilo.ai/api/gateway/models (live catalog, no auth — 371 models, `:free` rows verified 2026-09-05)
- https://kilo.ai/docs/gateway/models-and-providers
- https://kilo.ai/docs/gateway/api-reference
- http://kilo.ai/gateway
- https://freellms.org/providers/kilo-code/
- https://github.com/nejib1/Free-LLM
