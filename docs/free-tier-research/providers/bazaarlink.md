---
name: BazaarLink
url: "https://bazaarlink.ai"
api_base: "https://api.bazaarlink.ai/v1"
setup_instructions: |
  1. Sign up at https://bazaarlink.ai/free on the Free plan (no credit card) and create an API key.
  2. Point an OpenAI-compatible client at https://api.bazaarlink.ai/v1.
  3. Call a free model id below, or use `auto:free` for free-only routing (vision/image/video tiers are disabled in the free router).
api_key_url: "https://bazaarlink.ai/free"
limits:
  requests:
    minute: 10
---

BazaarLink has an official no-card Free plan with four enabled free models and a free-only `auto:free` router. Verified 2026-11-20.

**Free Tier:**

- Free — No Credit Card Required. Account + API key required.
- No credit: 10 RPM / 60 weighted units/day. With credit: 20 RPM / 120 weighted units/day. Shared across all free models.
- Daily reset 00:00 UTC; site-wide free cap 20 RPM, 2 concurrent free requests per account, plus an IP guard.
- Frontmatter records the no-credit 10 RPM default; the daily weighted-unit cap is documented here because it is not a plain request/token count.

**Free Models:**

- `qwen/qwen3.7-flash` — text/image/video, 1M context. Vision confirmed by the official free table (catalog said otherwise).
- `nvidia/nemotron-3.5-lightning-free` — text, 1M context.
- `stealth/glyph-cluster` — text, 256K context.
- `deepseek/deepseek-v4-flash-0731free` — text, 1,048,576 context.
- `auto:free` — official free routing table; it routes only among enabled free models.

Catalog IDs ending in `:free` for Qwen and DeepSeek are stale; use the exact ids above. Tool-calling support per model is not verified.

**Limits:**

- 60 weighted units/day is account-wide and shared. Weighting is per model, not documented as token counts — do not convert it.

**Notes:**

- Vision/image/video tiers are disabled in `auto:free` even though `qwen/qwen3.7-flash` itself supports them.

**Sources**

- https://bazaarlink.ai/free
- https://bazaarlink.ai/en/docs
- docs/free-tier-research/raw/freellmapi-catalog/platforms/bazaarlink.json (discovery lead, verified 2026-11-20)
