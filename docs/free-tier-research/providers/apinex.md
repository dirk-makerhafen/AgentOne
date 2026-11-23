---
name: Apinex
url: https://apinex.bond
api_base: https://api.apinex.bond/v1
setup_instructions: '1. Sign up at https://apinex.bond/pricing.md on the Free plan
  (no credit card; one-click Google/Telegram signup).

  2. Create an `sk-apx...` API key.

  3. Point an OpenAI-compatible client at https://api.apinex.bond/v1 and call POST
  /chat/completions with an `allowFree: true` route from GET https://apinex.bond/api/public/models.

  4. Check GET /v1/subscription for `token_limit`, `tokens_used`, `tokens_remaining`,
  `resets_at_utc` and `allowed`.

  '
api_key_url: https://apinex.bond/pricing.md
---

Apinex has an official free tier with `allowFree` zero-priced routes. Account + key required, no credit card. Verified 2026-11-20. **The widely advertised 25M tokens/day requires a $5 top-up plus daily check-in and is not a no-payment quota.**

**Sources**

- https://apinex.bond/for-ai.md
- https://apinex.bond/pricing.md
- https://apinex.bond/api/public/models
- https://apinex.bond/developers/balance
- https://apinex.bond/developers/errors.md
- https://apinex.bond/models/free-minimax-m3
- docs/free-tier-research/raw/freellmapi-catalog/platforms/apinex.json (discovery lead, verified 2026-11-20)
