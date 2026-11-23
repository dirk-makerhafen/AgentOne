---
name: Gonka Broker
url: https://gonkabroker.com
api_base: https://proxy.gonkabroker.com/v1
setup_instructions: '1. Sign up at https://app.gonkabroker.com/signup (phone verification
  required; free tier is $0, no credit card).

  2. Create an API key in the dashboard.

  3. Call the OpenAI-compatible endpoint at https://proxy.gonkabroker.com/v1 with
  the key as Bearer token.

  4. Live model list available at GET /v1/models (rotates with network governance).

  '
api_key_url: https://app.gonkabroker.com/signup
---

Gonka Broker is a decentralized inference broker with a permanent free tier (~1M tokens/month shared across models, resets monthly). Model lineup rotates with network governance; check `/v1/models` for current availability.

**Sources**

- https://gonkabroker.com (official site)
- https://app.gonkabroker.com/signup (signup)
- https://proxy.gonkabroker.com/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/Gonka Broker.json (discovery snapshot, verified 2026-09-05)
