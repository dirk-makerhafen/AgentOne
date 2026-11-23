---
name: Routeway
url: https://routeway.ai
api_base: https://api.routeway.ai/v1
setup_instructions: '1. Sign up at https://routeway.ai/dashboard on the Starter plan.

  2. Open Dashboard -> API Keys and create an API key (`sk-...`).

  3. Point an OpenAI-compatible client at https://api.routeway.ai/v1 and call a model
  id ending in `:free`.

  '
api_key_url: https://routeway.ai/dashboard/keys
---

Routeway is an OpenAI-compatible model gateway with a standing zero-cost `:free` route lane. The official FAQ caps free routes at 20 requests/minute and 200 requests/day (UTC midnight reset); the cap cannot be raised. Free routes are lower-priority and documented as development/testing only, with no SLA.

**Sources**

- https://routeway.ai/
- https://routeway.ai/models/cheapest
- https://docs.routeway.ai/getting-started/faq
- https://docs.routeway.ai/api-reference/overview
- docs/free-tier-research/raw/freellmapi-catalog/platforms/routeway.json (discovery lead, verified 2026-11-20)
