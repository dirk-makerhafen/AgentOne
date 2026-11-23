---
name: Waterfall
url: https://www.getwaterfall.org
api_base: https://api.getwaterfall.org/v1
setup_instructions: '1. Sign in at https://getwaterfall.org/dashboard on the Free
  plan (no payment info) and create an API key (`wf-sk-...`).

  2. Point an OpenAI-compatible client at https://api.getwaterfall.org/v1.

  3. To stay strictly on zero-cost models, send `extra_body={"routing_strategy": "free_smart"}`
  with `model: "auto"`, or select an exact `-free` model id with the `exact` strategy.

  4. Browse the live free catalogue at https://getwaterfall.org/models or GET https://api.getwaterfall.org/api/v1/models.

  '
api_key_url: https://getwaterfall.org/dashboard
---

Waterfall is an indie LLM router with a standing Free plan ($0/month, no card) and a curated, hourly-revalidated zero-cost pool. Verified 2026-11-20.

**Sources**

- https://www.getwaterfall.org/
- https://getwaterfall.org/docs/
- https://getwaterfall.org/pricing/
- https://getwaterfall.org/strategies
- https://getwaterfall.org/models
- https://api.getwaterfall.org/api/v1/models
- https://getwaterfall.org/trust
- docs/free-tier-research/raw/freellmapi-catalog/platforms/waterfall.json (discovery lead, verified 2026-11-20)
