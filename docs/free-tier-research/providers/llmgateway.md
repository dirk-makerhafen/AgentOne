---
name: LLM Gateway
url: "https://llmgateway.io"
setup_instructions: |
  1. Create an account and get an API key (LLMGATEWAY_API_KEY).
  2. Point an OpenAI-compatible client at https://api.llmgateway.io/v1.
  3. Use a free-tier model (no credit purchase needed).
api_key_url: "https://llmgateway.io"
limits: {}
---

LLM Gateway (open source, AGPLv3) is an OpenAI-compatible gateway: "Free models are available on the free tier without buying credits." Paid use is prepaid credits ($10 min) plus a flat 5% platform fee.

**Free Tier:**

- Free-tier models usable with $0 subscription and no credit purchase.
- BYOK (own provider keys) and self-hosting are free.

**Free Models:**

- Live catalog marks the free tier (observed: `claude-haiku-4-5-free` at $0 in fixtures) — resolve via https://llmgateway.io/models, not hardcoded here.

**Limits:**

- Published numerics for free-tier rates: none found on the pricing page.

**Notes:**

- Account required; API key required.
- Related paid products on the same platform: DevPass coding plans, Lounge chat memberships (not free API).

**Sources**

- https://llmgateway.io/pricing (free-tier sentence verified 2026-09-05)
- https://docs.llmgateway.io/
