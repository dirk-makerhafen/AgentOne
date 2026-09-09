---
name: FastRouter
url: "https://fastrouter.ai"
api_base: "https://api.fastrouter.ai/api/v1"
setup_instructions: |
  1. Create an account at https://fastrouter.ai and create an API key in the dashboard (one-time visible token — copy it immediately).
  2. IMPORTANT: top up paid credits so the organization holds a paid balance above $1 — free-model requests are blocked (402 insufficient_credits) at or below $1, even though free requests themselves cost $0.00.
  3. Call the OpenAI-compatible API at https://api.fastrouter.ai/api/v1 with the key.
  4. Use a `:free`-suffixed model ID for the free lane, or `fastrouter/free` to auto-select an eligible free model.
api_key_url: "https://fastrouter.ai"
limits:
  requests:
    day: 10
---

FastRouter is an OpenAI-compatible model router with a documented `:free` lane: selected models carry a Free badge and serve $0.00 requests under a small per-model daily quota.

**Free Tier:**

- Free lane on documented `:free`-suffixed models plus the `fastrouter/free` auto-router; free requests cost $0.00 and do not consume credits.
- ⚠ Payment-gated: the organization must hold a paid credit balance above $1 to use free models at all (402 otherwise). Whether signup free credits satisfy this is unverified — the docs say "paid credit balance".
- Account and API key required.

**Free Models (documented table verified 2026-09-05; `:free` is enabled per model — confirm live badges at https://fastrouter.ai/models?order=newest):**

- [`openai/gpt-oss-120b:free`](../models/gpt-oss-120b.md) — reasoning/agentic.
- [`openai/gpt-oss-20b:free`](../models/gpt-oss-20b.md) — reasoning/agentic.
- `google/gemma4-26b:free` — (no model card; not the same model as `gemma-4-31b-it`).
- `nvidia/nemotron-3-nano-30b:free` — see [model card](../models/nemotron-3-nano-30b-a3b.md) (provider ID differs from card default).
- [`nvidia/nemotron-3-super:free`](../models/nemotron-3-super-120b-a12b.md)
- `sarvam/sarvam-105b:free`
- `fastrouter/free` — router that auto-selects an eligible free model per request (consumes the selected model's free quota).
- Image/video models on the same endpoint are NOT documented as free — trust the official models page badges, not third-party fixtures.

**Limits:**

- 10 free requests per organization per free model per day, tracked independently per underlying model (frontmatter `day: 10` is this per-model quota, NOT an account-wide total). Resets daily at UTC midnight; no carry-over; quota may change periodically.
- Quota-exhausted models are excluded from `fastrouter/free` routing until reset; stripping `:free` falls back to paid billing.
- Remove `:free`/`:flex` mixing: the two suffixes are mutually exclusive.

**Notes:**

- Endpoint is `https://api.fastrouter.ai/api/v1` (not `go.fastrouter.ai`).
- Router/fallback model `fastrouter/auto` is not documented as free — do not use it as a free model.
- Free-model requests appear in the Activity Log with a Free tier indicator at $0.00 cost.
- Phone verification: unknown. Per-request context caps: undocumented.

**Sources**

- https://docs.fastrouter.ai/explore-features/free-model-router.md (free table, 10/day quota, >$1 balance gate verified 2026-09-05)
- https://fastrouter.ai/models?order=newest (live Free badges)
- https://fastrouter.ai/ (base URL `https://api.fastrouter.ai/api/v1`, free-credits positioning)
- https://github.com/fastrouter/docs (official docs repo: dashboard key creation)
