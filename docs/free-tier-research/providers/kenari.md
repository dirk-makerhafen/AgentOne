---
name: Kenari
url: "https://kenari.id"
setup_instructions: |
  1. Create an account at https://kenari.id/login (no foreign credit card needed; the free lane needs no top-up at all).
  2. In the dashboard open API keys and create a key (KENARI_API_KEY, `kn-...` prefix, shown only once — store it securely).
  3. Point an OpenAI-compatible client at https://kenari.id/v1 with `Authorization: Bearer kn-...` and call a `:free`-suffixed model ID (e.g. `step-3-7-flash:free`). Skip any balance top-up if you only use `:free` models.
api_key_url: "https://kenari.id/login"
limits: {}
---

Kenari (Indonesian gateway, billing in Rupiah) bills `:free`-suffixed models Rp 0 with per-minute caps plus three-tier daily quotas (Solo = never topped up / Payer / Subscription-plan quota).

**Free Tier:**

- `:free` models billed Rp 0; best-effort lane, no availability guarantees.
- No top-up needed for the free lane. Top-up via QRIS from Rp 1,000 — no foreign credit card needed (only relevant if you leave the free lane).
- Empty responses (no output tokens) are never billed on any tier.

**Free Models (live `GET /v1/models` catalog, verified 2026-09-05 — 13 `:free` IDs, all `"free": true`, none with `sunset_at` set):**

- [`glm-4-7-flash:free`](../models/glm-4.7-flash.md) — 131K context, reasoning + tool call.
- [`laguna-s-2-1:free`](../models/laguna-s-2.1.md) — 262K context, reasoning + tool call (Poolside Laguna S 2.1).
- [`laguna-xs-2-1:free`](../models/laguna-xs-2.1.md) — 262K context, reasoning + tool call (Poolside Laguna XS 2.1).
- [`step-3-7-flash:free`](../models/step-3-7-flash.md) — 262K context (official docs example), reasoning + tool call.
- [`nemotron-3-super-120b-a12b:free`](../models/nemotron-3-super-120b-a12b.md) — 262K context, reasoning + tool call (note: Super, not the Nano card model).
- [`nemotron-3-ultra-550b-a55b:free`](../models/nemotron-3-ultra-550b-a55b.md) — 1M context, reasoning + tool call.
- [`mimo-v2-5:free`](../models/mimo-v2.5.md) — ~1.05M context, reasoning + tool call.
- `mistral-medium-3-5:free` — 262K context, reasoning + tool call.
- [`hy3:free`](../models/hy3.md) — 262K context, reasoning + tool call (Tencent Hunyuan Hy3).
- [`agnes-2-5-flash:free`](../models/agnes-2.5-flash.md) — 512K context. (Deprecated `agnes-2-0-flash:free` legacy row still exists live but is deliberately not catalogued — superseded ≥1yr-old generation.)
- [`muse-spark-1-2-contributor:free`](../models/muse-spark-1.2-contributor.md) — ~1M context, reasoning + tool call.
- [`muse-spark-1-3-contributor:free`](../models/muse-spark-1.3-contributor.md) — ~1M context, reasoning + tool call.
- Only `:free`-suffixed IDs are free; same-name non-suffixed models are metered.

**Limits:**

- Per-minute request cap per `:free` model plus a daily request quota in three tiers by account status (Solo = never topped up / Payer / Subscription-plan quota).
- Live numbers are operator-set on https://kenari.id/plan (also `GET /api/public/pricing`) — not hardcoded here.
- Exhaustion returns HTTP 429 with `Retry-After` and reason `free_quota_daily`.

**Notes:**

- Account required; API key required (`kn-...`, one key covers all models and both OpenAI- and Anthropic-style APIs); docs are Indonesian-first (English toggle available).
- OpenAI-compatible plus Anthropic-messages and Responses wire formats; BYOK route is free (own key billed by provider).
- Fixture leads (not authoritative, absent from the live catalog 2026-09-05): `deepseek-v4-flash:free` and `deepseek-v4-pro:free` appear at $0 in `raw/opencode-models-api/kenari/` but are not listed live — re-check `GET /v1/models` before use. Likewise `kimi-k2-7-code:free`, `kimi-k2-6:free`, and `mistral-large:free` (listed in the previous revision) are not in the live catalog today.
- Non-suffixed fixture entries at $0 (e.g. `minimax-m3`, `gemma-4-31b-it`, `gpt-oss-120b` without `:free`) are not documented as free — per Kenari docs only `:free` IDs are Rp 0, so they are not claimed here.
- Each catalog entry carries a `sunset_at` epoch; a model serves until that time passes, then disappears from the catalog — check it before pinning an ID.

**Sources**

- https://kenari.id/docs/billing (free-version + quota tiers, verified 2026-09-05)
- https://kenari.id/docs/models (live-catalog rule, `:free` semantics, verified 2026-09-05)
- https://kenari.id/docs/quickstart (signup, `kn-` key, `:free` without top-up, `https://kenari.id/v1` base URL, verified 2026-09-05)
- https://kenari.id/docs/authentication (`kn-` key management, Bearer auth, verified 2026-09-05)
- https://kenari.id/v1/models (live catalog queried 2026-09-05: 72 models, 13 `:free` IDs with `"free": true`)
