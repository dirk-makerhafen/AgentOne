---
name: ZenMux
url: "https://zenmux.ai"
api_base: "https://zenmux.ai/api/v1"
setup_instructions: |
  1. Sign in at https://zenmux.ai/login (email, GitHub, or Google; no payment information required for the free lane).
  2. Create an API key in the ZenMux console (Pay As You Go management page / platform management).
  3. POST to https://zenmux.ai/api/v1/chat/completions (OpenAI-compatible) with {"model": "<provider>/<slug>", ...} and "Authorization: Bearer <key>". Anthropic protocol at /api/anthropic, Gemini protocol at /api/vertex-ai.
  4. Free-lane models are billed $0 per token, marked "Free" with a "Rate Limit" badge on the model page, and are usable without a prepaid balance; only paid models require a PAYG top-up or the Builder subscription.
api_key_url: "https://zenmux.ai/platform/pay-as-you-go"
---

ZenMux is a model aggregation router (OpenAI/Anthropic/Gemini-compatible) that runs a "Free" lane: a rotating set of models billed at $0/M tokens, rate-limited, available after a simple sign-in plus API key with no payment information.

**Free Tier:**

- Free-lane models are priced at $0 input and $0 output (per-token), marked "Free" + "Rate Limit" on the model detail page.
- Rate limits apply to the free lane and are not published numerically; the roster rotates and models can move between free/paid lanes or disappear without notice.
- The same model slug may expose both a free provider lane (e.g. `z-ai` at $0) and paid lanes (e.g. `bigmodel`); router/preference selects the lane.
- Paid models (non-free slugs) require a prepaid PAYG balance or the Builder subscription — those are outside this provider's free scope.

**Free Models (live catalog verified 2026-09-06 via `GET https://zenmux.ai/api/v1/models`; roster rotates — re-check live):**

- [`z-ai/glm-4.7-flash-free`](../models/glm-4.7-flash.md) — 200K context, $-free Z.ai lane, rate-limited
- `z-ai/glm-4.6v-flash-free` — GLM-4.6V vision model, 200K context, rate-limited (vision specialist, not catalogued)
- [`sapiens-ai/agnes-2.5-flash`](../models/agnes-2.5-flash.md) — 524K context, $0, rate-limited
- [`dots-studio/dots3-note-prev`](../models/dots-3-note.md) — Dots3-Note preview, ~393K context, $0, rate-limited
- `inclusionai/ling-3.0-tiny` — Ling-3.0 tiny variant, 262K context, $0 (small variant, not catalogued)
- Embeddings at $0: `openai/text-embedding-3-small`, `openai/text-embedding-3-large`, `google/gemini-embedding-2`, `qwen/qwen3-vl-embedding`

**Limits:**

- Free lane: rate-limited (per-module or per-model); exact limits not published. **Never assume a specific RPM/RPD — a single number is not documented.**
- Free-lane availability is time-limited and rotating.

**Notes:**

- Account required; API key required; no payment information required for the free lane (verified 2026-09-06).
- OpenAI-compatible at `https://zenmux.ai/api/v1`; Anthropic and Gemini protocols also supported on the same key.
- Free-lane model IDs end in `-free` or are otherwise zero-priced (`-prev` previews); paid slugs are NOT free even though they share a model family with a free lane.
- Time-limited promos have appeared (e.g. `z-ai/glm-5.3-free`, `deepseek/deepseek-v4-flash-vision-exp-free`, "Free 1 Week" banners) — promotional/trial windows are not catalogued as free rows.

**Sources**

- https://zenmux.ai/models (live free roster, filters, model detail pages verified 2026-09-06)
- https://zenmux.ai/docs/guide/quickstart.html (sign-in, API key, plans, base URLs)
- https://zenmux.ai/z-ai/glm-4.7-flash-free ($0 free lane, rate-limit badge, 200K context)
- https://zenmux.blog/blog (official blog "4 Truly Free LLM APIs" — free lane terms; rate-limited)
- https://zenmux.ai/pricing/overview