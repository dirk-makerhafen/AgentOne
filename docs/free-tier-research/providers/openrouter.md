---
name: OpenRouter
url: "https://openrouter.ai"
setup_instructions: |
  1. Create an account at https://openrouter.ai (email signup; no credit card required for free models).
  2. Create an API key at https://openrouter.ai/keys.
  3. Optional: purchase at least $10 in credits at https://openrouter.ai/settings/credits to raise the free-model allowance from 50 to 1,000 requests/day.
  4. POST to https://openrouter.ai/api/v1/chat/completions with {"model": "<slug>:free", ...} and "Authorization: Bearer <key>".
  5. Check quota/credit status anytime via GET https://openrouter.ai/api/v1/key.
api_key_url: "https://openrouter.ai/keys"
limits:
  requests:
    minute: 20
    day: 50
---

OpenRouter exposes free (`:free`-suffixed) variants of models through its unified OpenAI-compatible API, with low rate limits that rise after $10 in lifetime credit purchases.

**Free Tier:**

- Permanent `:free` model variants ($0 inference), not trial credits; new users also get a small one-time free allowance.
- Free-model caps apply account-wide; extra accounts/keys do not raise them.
- Free variants are best-effort: paid traffic gets priority, and drained/upstream-exhausted pools return 429 (automatic provider fallback is attempted first).

**Free Models (live catalog verified 2026-09-05 via `GET https://openrouter.ai/api/v1/models`; roster rotates — re-check live or at https://openrouter.ai/models?max_price=0):**

- [`cohere/north-mini-code:free`](../models/north-mini-code.md)
- [`dots-studio/dots-3-note-preview:free`](../models/dots-3-note.md)
- `google/gemma-4-26b-a4b-it:free`
- [`google/gemma-4-31b-it:free`](../models/gemma-4-31b-it.md)
- [`inclusionai/ling-3.0-flash-fin:free`](../models/ling-3.0-flash-fin.md) / [`inclusionai/ling-3.0-flash-sante:free`](../models/ling-3.0-flash-sante.md)
- [`liquid/lfm-2.5-2.6b:free`](../models/lfm-2.5.md)
- [`minimax/minimax-m2.7:free`](../models/minimax-m2.7.md)
- [`minimax/minimax-m3:free`](../models/minimax-m3.md)
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — Nemotron 3 Nano reasoning variant; see [model card](../models/nemotron-3-nano-30b-a3b.md) (provider ID differs from card default)
- [`nvidia/nemotron-3-super-120b-a12b:free`](../models/nemotron-3-super-120b-a12b.md) / [`nvidia/nemotron-3-ultra-550b-a55b:free`](../models/nemotron-3-ultra-550b-a55b.md) / [`nvidia/nemotron-3.5-lightning:free`](../models/nemotron-3.5-lightning.md). (`nvidia/nemotron-3.5-content-safety:free` remains a free row but is a 4B guardrail specialist, deliberately not catalogued as a model card.)
- [`poolside/laguna-s-2.1:free`](../models/laguna-s-2.1.md) — Laguna S 2.1; see [model card](../models/laguna-s-2.1.md)
- [`poolside/laguna-xs-2.1:free`](../models/laguna-xs-2.1.md) — Laguna XS 2.1; see [model card](../models/laguna-xs-2.1.md)
- [`thinkingmachines/inkling:free`](../models/inkling.md) / [`thinkingmachines/inkling-small:free`](../models/inkling-small.md)
- [`z-ai/glm-5.2:free`](../models/glm-5.2.md)
- `openrouter/free` router auto-selects a free model.

**Limits:**

- Free variants: 20 requests/min always; 50 requests/day with < $10 lifetime purchased credits; 1,000 requests/day with >= $10 purchased credits (frontmatter `day: 50` is the no-purchase baseline).
- Paid variants have no platform request cap; Cloudflare DDoS protection applies to all requests.
- Negative credit balance returns 402 even on free models; 429 indicates a platform cap or upstream provider exhaustion.

**Notes:**

- Account required; API key required; no payment required for free models.
- Fully OpenAI-compatible (`/api/v1/chat/completions`, `/api/v1/models`, `GET /api/v1/key` for quota/credit checks).
- Privacy: prompts/completions not logged by default (opt-in logging earns 1% discount); requests route only to providers matching the account's model-training privacy setting.
- Credit purchase fee ~5.5% via Stripe ($0.80 minimum) / 5% crypto; unused credits may expire after one year; refunds only within 24h.

**Sources**

- https://openrouter.ai/docs/api_reference/limits (20 RPM, 50/1,000 per day, $10 threshold verified 2026-09-05)
- https://openrouter.ai/docs/faq (free-tier terms, privacy, fees verified 2026-09-05)
- https://openrouter.ai/docs/guides/routing/model-variants/free
- https://openrouter.ai/api/v1/models (live `:free` roster enumerated 2026-09-05)
- https://openrouter.ai/docs (quickstart)
