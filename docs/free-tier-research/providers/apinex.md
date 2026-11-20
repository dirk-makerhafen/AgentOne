---
name: Apinex
url: "https://apinex.bond"
api_base: "https://api.apinex.bond/v1"
setup_instructions: |
  1. Sign up at https://apinex.bond/pricing.md on the Free plan (no credit card; one-click Google/Telegram signup).
  2. Create an `sk-apx...` API key.
  3. Point an OpenAI-compatible client at https://api.apinex.bond/v1 and call POST /chat/completions with an `allowFree: true` route from GET https://apinex.bond/api/public/models.
  4. Check GET /v1/subscription for `token_limit`, `tokens_used`, `tokens_remaining`, `resets_at_utc` and `allowed`.
api_key_url: "https://apinex.bond/pricing.md"
limits:
  requests:
    minute: 15
---

Apinex has an official free tier with `allowFree` zero-priced routes. Account + key required, no credit card. Verified 2026-11-20. **The widely advertised 25M tokens/day requires a $5 top-up plus daily check-in and is not a no-payment quota.**

**Free Tier:**

- All accounts start at 15 RPM account-wide, shared across keys, in a fixed 60-second window. Frontmatter records this verified cap.
- A daily free allowance exists and is inspectable via `GET /v1/subscription`, but the no-payment token amount is **unpublished** — official marketing only says "free starter credits". Do not record 25M/day as free.
- Free routes consume a separate weighted allowance (per-model weights 2x-5x); some `free/*` ids have `allowFree: false` and need a subscription.

**Free Models:**

`GET https://apinex.bond/api/public/models` showed 15 `allowFree: true` zero-priced routes on 2026-11-20, including:

- `free/glm-5.3-flashx`, `free/hy4-flash`, `free/gemini-4-hydrogen`, `free/mimo-v2.6-pro`, `free/qwen-3.8-max`, `free/kimi-k3`, `free/deepseek-v4.1-flash`, `free/gemini-3.8-flash`, `free/glm-5.3-flash`, `free/deepseek-v4-pro-0813`, `free/muse-spark-1.3`, `free/hy4`, `free/minimax-m3.1-flash`, `free/gpt-6-luna`, `free/jev-1.13`.

Live official catalog marks most of these tool-capable and often vision-capable, contradicting the catalog's all-false flags.

**Limits:**

- 15 RPM is account-wide, not per key. No no-payment token quota is published; do not infer one.
- Catalog's 5 RPM and 10M weighted/day are stale/unverified.

**Notes:**

- The $5 top-up / 25M/day / check-in offer is a promotional paid-gated enhancement, excluded from the free assessment.
- Model availability and `allowFree` flags can change; re-check the public model endpoint before relying on an id.

**Sources**

- https://apinex.bond/for-ai.md
- https://apinex.bond/pricing.md
- https://apinex.bond/api/public/models
- https://apinex.bond/developers/balance
- https://apinex.bond/developers/errors.md
- https://apinex.bond/models/free-minimax-m3
- docs/free-tier-research/raw/freellmapi-catalog/platforms/apinex.json (discovery lead, verified 2026-11-20)
