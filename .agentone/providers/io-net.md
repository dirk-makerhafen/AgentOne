---
name: IO Intelligence
url: "https://io.net"
api_base: "https://api.intelligence.io.solutions/api/v1"
setup_instructions: |
  1. Sign up for an io.net account (starts on the free Standard plan by default).
  2. Create an API key in the dashboard under API Keys (set a name, project "IO Intelligence", permissions, and an expiry of 30/60/90/180 days).
  3. Call the OpenAI-compatible API at https://api.intelligence.io.solutions/api/v1 with the key as Bearer token.
  4. Resolve current model IDs and per-model credit burn rates live via GET /models (input_token_price / output_token_price fields).
api_key_url: "https://ai.io.net/ai/api-keys"
limits: {}
---

IO Intelligence (io.net's inference product) puts new accounts on a free Standard plan by default: light daily access from an auto-refreshing shared credit pool, with pay-as-you-go via IO Credits once the daily allowance is exceeded.

**Free Tier:**

- Standard (default) plan: free light daily access; PAYG pricing applies to usage beyond the daily limit.
- Shared credit pool across all models (per-model credit burn rates differ); chat interactions count toward the same API quota.
- Professional ($15/mo credits, daily refresh) and Developer ($150/mo credits, 8-hour refresh) raise the allowance.

**Free Models:**

- Same model catalog on all plans — any catalog model draws from the free daily pool within the allowance. Resolve IDs and pricing live via `GET /models` (roster and rates not hardcoded here).

**Limits:**

- No numeric free-allowance figures are published on the payments page (plan tables carry the current figures — check live). The API FAQ states free daily limits vary per model; the referenced API-reference table carries no numerics. Frontmatter limits omitted deliberately.

**Notes:**

- Account required; API key required; payment method only needed if you exceed the free daily access (PAYG via IO Credits balance).
- Plan-table ambiguity (2026-09-05): the intro describes Standard as free light daily access with PAYG beyond the daily limit, while the plan overview table row reads "Continuous access with PAYG — no refreshes, pay only for what you use." Treat exact Standard refresh semantics as unconfirmed; check the live plan table.
- Endpoint `https://api.intelligence.io.solutions/api/v1` confirmed by the official API reference Python/cURL examples. Env var: `IOINTELLIGENCE_API_KEY`.

**Sources**

- https://io.net/docs/guides/payment/io-intelligence-payments (free Standard plan + shared pool, verified 2026-09-05)
- https://io.net/docs/reference/ai-models/get-started-with-io-intelligence-api (endpoint, key creation at ai.io.net/ai/api-keys, verified 2026-09-05)
- https://io.net/docs/guides/intelligence/io-intelligence-apis (key creation steps, endpoint, verified 2026-09-05)
