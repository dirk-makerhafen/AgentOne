---
name: Kilo Code
url: "https://kilo.ai"
default_api_key: public
setup_instructions: |
  1. No signup needed for anonymous free access — call the gateway directly (rate-limited per IP).
  2. Optional: sign in at https://app.kilo.ai to obtain a JWT API key for keyed use and paid models.
  3. Point any OpenAI-compatible client at https://api.kilo.ai/api/gateway with `model` set to `kilo-auto/free` or a `:free` model ID.
  4. Send `Authorization: Bearer $KILO_API_KEY` when using a key; omit it for anonymous `:free` calls.
api_key_url: "https://app.kilo.ai"
limits:
  requests:
    hour: 200
---

Kilo Code's Kilo Gateway is a unified OpenAI-compatible API over 500+ models with a permanent $0/forever free tier, including keyless anonymous access to models tagged `:free`.

**Free Tier:**

- Permanent free models at $0/forever — not trial credits.
- `kilo-auto/free` router resolves each session to a curated free model with no credits required.
- Anonymous (no key, IP-identified) access permitted for `:free` models only.

**Free Models:**

- `stepfun/step-3.7-flash:free` (representative, verify live; roster rotates server-side).
- [`poolside/laguna-s-2.1:free`](../models/laguna.md) (representative, verify live).
- [`poolside/laguna-xs-2.1:free`](../models/laguna.md) (representative, verify live).
- `nvidia/nemotron-3-ultra-550b-a55b:free` (representative, verify live).
- `tencent/hy3:free` (representative, verify live).
- `openrouter/free` — best-available-free-model alias (representative, verify live).
- `kilo-auto/free` — dynamic free-model router, no credits required.
- Full current list (no auth): `GET https://api.kilo.ai/api/gateway/models`.

**Limits:**

- Anonymous `:free` access: 200 requests/hour per IP (official docs).
- Authenticated free-model limits: unknown — not published.

**Notes:**

- No account, key, payment, or phone required for anonymous `:free` calls; key required for paid models.
- Data handling: Auto Free may route to providers that log prompts/outputs for service improvement; NVIDIA free endpoints are trial-use only with session logging under NVIDIA API Trial Terms — do not submit personal or confidential data on free routes.
- Free-model roster and `kilo-auto` routing change server-side without notice.
- No credit card required.

**Sources**

- https://kilo.ai/docs/gateway/models-and-providers
- https://kilo.ai/docs/gateway/authentication
- https://kilo.ai/docs/gateway/api-reference
- https://kilo.ai/docs/getting-started/using-kilo-for-free
- http://kilo.ai/gateway
- https://freellms.org/providers/kilo-code/
- https://github.com/nejib1/Free-LLM
