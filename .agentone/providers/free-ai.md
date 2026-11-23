---
name: Free.ai
url: https://free.ai
api_base: https://api.free.ai
setup_instructions: '1. Enter your email at https://free.ai/api and confirm the sign-in
  link (no card, no password).

  2. Generate an `sk-free-...` key.

  3. POST to https://api.free.ai/v1/chat/ with `Authorization: Bearer sk-free-...`
  and `model: "qwen7b"`.

  4. Only self-hosted models are free; `premium/...` and external models consume purchased
  tokens.

  '
api_key_url: https://free.ai/api
---

Free.ai (Muddy Holdings LLC) is an aggregator with a genuine free allowance on its self-hosted models. Account + key required for the 30K/day allowance; no card. Verified 2026-11-20.

**Sources**

- https://free.ai/api
- https://api.free.ai/v1/models
- https://free.ai/models
- https://free.ai/docs
- docs/free-tier-research/raw/freellmapi-catalog/platforms/freeai.json (discovery lead, verified 2026-11-20)
