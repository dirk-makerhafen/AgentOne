---
name: IO Intelligence
url: "https://io.net"
setup_instructions: |
  1. Create an io.net account (Standard plan is the free default).
  2. Create an API key (IOINTELLIGENCE_API_KEY).
  3. Call the API at https://api.intelligence.io.solutions/api/v1 with the key.
api_key_url: "https://io.net"
limits: {}
---

IO Intelligence (io.net's inference product) defaults new accounts to a free Standard plan: light daily access from an auto-refreshing shared credit pool, with pay-as-you-go beyond the daily limit.

**Free Tier:**

- Standard (default) plan: free light daily access; credits refresh automatically; no token tracking needed by the user.
- Usage beyond the daily allowance bills pay-as-you-go via IO Credits balance.
- Shared credit pool across all models (rates differ per model); chat interactions count toward the same API quota.

**Free Models:**

- Same model catalog on all plans (per-model credit burn rates differ) — resolve pricing live via the `GET /models` endpoint (`input_token_price` / `output_token_price` fields).

**Limits:**

- Published numerics for the free daily allowance: none on the payments page (plan tables carry the current figures — check live).

**Notes:**

- Account required; API key required; payment method only needed if you exceed the free daily access (PAYG).
- Professional ($15/mo credits, daily refresh) and Developer ($150/mo, 8-hour refresh) raise the allowance.

**Sources**

- https://io.net/docs/guides/payment/io-intelligence-payments (free Standard plan verified 2026-09-05)
- https://io.net/docs/guides/intelligence/io-intelligence-apis
