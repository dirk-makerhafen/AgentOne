---
name: OrcaRouter
url: "https://www.orcarouter.ai"
setup_instructions: |
  1. Sign up at https://www.orcarouter.ai with GitHub (Hacker tier is free forever, no credit card).
  2. Create an API key.
  3. Point an OpenAI-compatible client at https://api.orcarouter.ai/v1 and call a `-free` model ID (e.g. `deepseek/deepseek-v4-flash-free`) or the `orcarouter/free` named router. If the key has an allowed-model list, add `orcarouter/free` itself — whitelisting pool members does not unlock the router.
api_key_url: "https://www.orcarouter.ai"
limits:
---

OrcaRouter is an AI gateway (200+ models, one OpenAI-compatible API) whose Hacker tier is free forever with no credit card. Models with IDs ending in `-free` are ordinary catalog models priced at $0 — same weights and capabilities as the paid model they shadow — plus a built-in `orcarouter/free` named router over the free tier.

**Free Tier:**

- Hacker tier: free forever, no credit card; GitHub signup; API key required.
- Token usage on paid models is billed at the upstream provider rate ($0 markup, requires top-up); `-free` IDs never touch the wallet.
- Accounts that never topped up get a deliberately small daily allowance but remain usable.

**Free Models:**

- `deepseek/deepseek-v4-flash-free` — $0; see [model card](../models/deepseek-v4-flash.md).
- `deepseek/deepseek-v4-pro-free` — $0; see [model card](../models/deepseek-v4-pro.md).
- `orcarouter/free` — built-in named router scoring request difficulty across the free pool; never escapes to a paid model.
- The free set rotates — the `/v1/models` and `/api/pricing` catalogs are the source of truth, not this list.
- NOT free: `orcarouter/auto` is a per-workspace adaptive router over every model the account can access (paid included) — do not document it as a free model despite discovery-fixture cost-0 rows.

**Limits:**

- None published as numbers, by design — build for the `429` rather than counting. Frontmatter limits omitted deliberately.
- Caps are threefold: per-workspace per-minute + per-day buckets (day rolls at 00:00 UTC); tiered by lifetime spend (never-topped-up = small daily allowance); plus a per-request prompt-token cap on the lower tier (long prompts fail regardless of waiting).
- Rejections return `429` with code `free_rate_limited`: with a `Retry-After` header, wait exactly that many seconds and retry once (no exponential backoff — windows refill at the boundary); without it, the prompt exceeds the free prompt cap — shorten it, never retry unchanged.
- Free-tier limits apply to free IDs only and never affect paid traffic.

**Notes:**

- Free models never fall back to a paid model, and a `-free` ID cannot be a fallback target in an `extra_body.models` chain.
- Account required; API key required; no credit card for the Hacker tier.

**Sources**

- https://docs.orcarouter.ai/routing/free-models (verified 2026-09-05)
- https://www.orcarouter.ai/pricing
- https://docs.orcarouter.ai/routing/auto-router
- https://docs.orcarouter.ai/routing/named-routers
