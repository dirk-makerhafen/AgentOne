---
name: Aion Labs
url: https://www.aionlabs.ai/
api_base: https://api.aionlabs.ai/v1
setup_instructions: '1. Sign up at https://www.aionlabs.ai/accounts/signup/ (Free
  tier is the default on signup, $0, no card required).

  2. Open the dashboard and create an API key at API Keys (https://www.aionlabs.ai/app/api-keys/).

  3. Point any OpenAI-compatible client at base URL https://api.aionlabs.ai/v1 with
  the key as Bearer token (`Authorization: Bearer YOUR_API_KEY`; the `Api-Key` header
  prefix is also accepted).

  4. Call `POST /v1/chat/completions` (or `POST /v1/responses`) with an `aion-labs/`
  model ID. `GET /v1/models` needs no auth.

  '
api_key_url: https://www.aionlabs.ai/app/api-keys/
---

Aion Labs is an independent provider offering its proprietary Aion model family (roleplay/storytelling-specialized) through an OpenAI-compatible REST API at `https://api.aionlabs.ai/v1`. All claims below re-verified against official docs 2026-09-05.

**Sources**

- https://www.aionlabs.ai/docs/ (OpenAI-compatible API)
- https://www.aionlabs.ai/pricing/ (Free tier $0, daily credit allowance, no card)
- https://www.aionlabs.ai/docs/models/ (model list, context, prices, release dates)
- https://www.aionlabs.ai/docs/rate-limits/ (tier table: Free 15 RPM / 20K TPM / 20K daily)
- https://www.aionlabs.ai/docs/quickstart/ (dashboard key creation, base URL, Bearer auth)
- https://www.aionlabs.ai/docs/api-reference/ (auth rules incl. `Api-Key` prefix, endpoints, reasoning params)
- https://freellms.org/providers/aion-labs
- https://github.com/nejib1/Free-LLM
