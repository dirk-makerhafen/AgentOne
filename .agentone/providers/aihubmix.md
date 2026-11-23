---
name: AIHubMix
url: https://aihubmix.com
api_base: https://aihubmix.com/v1
setup_instructions: '1. Create an account at https://aihubmix.com (email or OAuth;
  no credit card required). Every account starts with 10 trial calls shared across
  all free models (never expire).

  2. Create an API key on the API Keys page (https://console.aihubmix.com/token);
  format `sk-...`. One key works for free and paid models.

  3. Call the OpenAI-compatible API at https://aihubmix.com/v1 with a `-free` model
  ID (e.g. `coding-glm-5.3-free`).

  4. For sustained use: make a one-time top-up of any amount from $1 — the account
  permanently switches to daily quotas (10 req/min, 100 req/day, 1M tokens/day shared
  across the free catalog, reset daily). Backup domain if needed: https://api.inferera.com.

  '
api_key_url: https://console.aihubmix.com/token
---

AIHubMix is a gateway over 870+ models with a "56 free models — no credit card required" lane; every free model bills $0/M input/output, subsidized by the platform (free page updated 2026-09-04, verified 2026-09-05).

**Sources**

- https://aihubmix.com/models/free (56 models, 10 trial calls, $1 top-up → 10/min + 100/day + 1M tokens/day, 429 behavior, updated 2026-09-04, verified 2026-09-05)
- https://docs.aihubmix.com/en/quick-start (endpoint https://aihubmix.com/v1, key page https://aihubmix.com/token verified 2026-09-05)
- https://docs.aihubmix.com/en/blogs/free-ai-models (no card, no trial expiry, RPM + daily token caps verified 2026-09-05)
- https://aihubmix.com/models (56-free-lane banner, per-model trial-use 429 rows verified 2026-09-05)
