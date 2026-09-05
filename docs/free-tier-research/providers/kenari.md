---
name: Kenari
url: "https://kenari.id"
setup_instructions: |
  1. Create an account at https://kenari.id/login (free Solo tier — never topped up — is enough for the free lane).
  2. Create an API key (KENARI_API_KEY).
  3. Call the API at https://kenari.id/v1 with the key and a `:free`-suffixed model ID.
api_key_url: "https://kenari.id"
limits: {}
---

Kenari (Indonesian gateway, billing in Rupiah) bills `:free`-suffixed models Rp 0 with per-minute caps plus three-tier daily quotas (Solo / Payer / Subscription).

**Free Tier:**

- `:free` models (e.g. `step-3-7-flash:free`) billed Rp 0; best-effort lane, no availability guarantees.
- Top-up via QRIS from Rp 1,000 — no foreign credit card needed (only relevant if you leave the free lane).
- Empty responses (no output tokens) are never billed on any tier.

**Free Models (verify live via `GET /v1/models`):**

- [`deepseek-v4-flash:free`](../models/deepseek-v4-flash.md), [`deepseek-v4-pro:free`](../models/deepseek-v4-pro.md) (observed in fixtures).
- `step-3-7-flash:free` (official docs example).
- Live-catalog `:free` IDs observed 2026-09-05 (discovery data, confirm via `GET /v1/models` before use): `kimi-k2-7-code:free`, `kimi-k2-6:free`, `mistral-medium-3-5:free`, `hy3:free`, `mistral-large:free`, `mimo-v2-5:free`, `nemotron-3-super-120b-a12b:free`, `glm-4-7-flash:free`.
- Only `:free`-suffixed IDs are free; same-name non-suffixed models are metered.

**Limits:**

- Per-minute request cap per `:free` model plus a daily request quota in three tiers by account status (Solo = never topped up / Payer / Subscription-plan quota).
- Live numbers are operator-set on https://kenari.id/plan (also `GET /api/public/pricing`) — not hardcoded here.
- Exhaustion returns HTTP 429 with `Retry-After` and reason `free_quota_daily`.

**Notes:**

- Account required; API key required; docs are Indonesian-first (English toggle available).
- OpenAI-compatible plus Anthropic-messages and Responses wire formats; BYOK route is free (own key billed by provider).

**Sources**

- https://kenari.id/docs/billing (free-version + quota section verified 2026-09-05)
- https://kenari.id/docs/models
