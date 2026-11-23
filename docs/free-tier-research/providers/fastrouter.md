---
name: FastRouter
url: https://fastrouter.ai
api_base: https://api.fastrouter.ai/api/v1
setup_instructions: '1. Create an account at https://fastrouter.ai and create an API
  key in the dashboard (one-time visible token — copy it immediately).

  2. IMPORTANT: top up paid credits so the organization holds a paid balance above
  $1 — free-model requests are blocked (402 insufficient_credits) at or below $1,
  even though free requests themselves cost $0.00.

  3. Call the OpenAI-compatible API at https://api.fastrouter.ai/api/v1 with the key.

  4. Use a `:free`-suffixed model ID for the free lane, or `fastrouter/free` to auto-select
  an eligible free model.

  '
api_key_url: https://fastrouter.ai
---

FastRouter is an OpenAI-compatible model router with a documented `:free` lane: selected models carry a Free badge and serve $0.00 requests under a small per-model daily quota.

**Sources**

- https://docs.fastrouter.ai/explore-features/free-model-router.md (free table, 10/day quota, >$1 balance gate verified 2026-09-05)
- https://fastrouter.ai/models?order=newest (live Free badges)
- https://fastrouter.ai/ (base URL `https://api.fastrouter.ai/api/v1`, free-credits positioning)
- https://github.com/fastrouter/docs (official docs repo: dashboard key creation)
