---
name: xKiro
url: "https://xkiro.com"
api_base: "https://api.xkiro.com/v1"
setup_instructions: |
  1. Sign up at https://xkiro.com/dashboard (no credit card) and create an API key (`sk-xt-...`).
  2. Call https://api.xkiro.com/v1/chat/completions with `Authorization: Bearer <key>` (or `x-api-key`).
  3. GET /v1/models is public; filter rows where `access_tier: free` and keep the `vendor/` prefix in model ids.
  4. Optional: verify Telegram in the dashboard to double the daily free-token allowance.
api_key_url: "https://xkiro.com/dashboard"
limits:
  tokens:
    day: 500000
---

xKiro is an OpenAI-compatible (plus Anthropic Messages) gateway with a documented permanent Free plan: 26 free models available to every account, 500,000 free tokens/day, no card. Verified 2026-11-20.

**Free Tier:**

- 500,000 tokens/day shared account-wide across all free models; Telegram verification doubles it to 1,000,000/day. Docs describe the window as sliding; marketing expresses it as per-day. Do not convert to RPM.
- Account + key required; no credit card. Paid models return `403 permission_denied` on the Free plan while free models continue to work.
- `GET /v1/usage` exposes `free_tokens.used_today`, `limit_per_day`, and `remaining` at no cost.
- On allowance exhaustion, free requests return `429` with `Retry-After`.

**Free Models:**

All 9 catalog leads were confirmed free in the live official catalogue (`access_tier: free`, input/output price 0) on 2026-11-20. Official capabilities/context (catalog values were partly stale):

- `mistralai/mistral-large-2512` — 256K context, tools + vision, 16,384 max output.
- `mistralai/mistral-medium-3.5` — 256K, tools + vision, reasoning (`none`/`high`), 65,536 output.
- `mistralai/mistral-small-2603` — 256K, tools + vision, reasoning (`none`/`high`), 65,536 output.
- `mistralai/codestral-2508` — 256K, tools, 16,384 output.
- `mistralai/devstral-medium` — 256K, tools, 16,384 output.
- `mistralai/ministral-14b` — 256K, tools + vision, 8,192 output.
- `mistralai/ministral-8b` — 256K, tools + vision, 8,192 output.
- `mistralai/ministral-3b` — 128K, tools + vision, 8,192 output.
- `sensenova/sensenova-6.8-flash-lite` — 262,144, tools + vision, reasoning (`none`/`low`/`medium`/`high`, default medium), 65,536 output.
- 17 additional free models not in the catalog include `cohere/command-a-plus`, `cohere/command-a`, `cohere/command-a-reasoning`, `cohere/command-a-vision`, `cohere/north-mini-code`, and `stealth/big-pickle`.

**Limits:**

- Frontmatter records the documented 500K tokens/day; the Telegram-verified 1M/day is an account upgrade, not the default.
- No RPM/RPD is published; do not infer one.

**Notes:**

- Model ids require the `vendor/` prefix; bare ids 404.
- Both OpenAI Chat Completions and Anthropic Messages are served. `GET /v1/models` is public and identical for all users.
- Free-token and wallet/PAYG spend windows are separate budgets.
- A secondary freellmapi doc claims 5M tokens/day; that figure corresponds to a PAYG example, not the Free plan. Official docs win.

**Sources**

- https://xkiro.com/
- https://docs.xkiro.com/api/overview/
- https://docs.xkiro.com/api/usage/
- https://docs.xkiro.com/api/rate-limits/
- https://docs.xkiro.com/models/
- https://docs.xkiro.com/models/tiers/
- https://api.xkiro.com/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/xkiro.json (discovery lead, verified 2026-11-20)
