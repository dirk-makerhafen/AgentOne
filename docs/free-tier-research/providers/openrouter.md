---
name: OpenRouter
url: "https://openrouter.ai"
setup_instructions: |
  1. Create an account at https://openrouter.ai.
  2. Create an API key at https://openrouter.ai/keys (new users get a small free allowance).
  3. Optional: purchase at least $10 in credits to raise free-model limits from 50 to 1,000 requests/day.
  4. POST to https://openrouter.ai/api/v1/chat/completions with {"model": "<slug>:free", ...} and "Authorization: Bearer <key>".
api_key_url: "https://openrouter.ai/keys"
limits:
  requests:
    minute: 20
    day: 50
---

OpenRouter exposes free (`:free`-suffixed) variants of models through its unified OpenAI-compatible API, with low rate limits that rise after $10 in lifetime credit purchases.

**Free Tier:**

- Permanent `:free` model variants ($0 inference), not trial credits; new users also get a small free allowance.
- Free-model caps apply account-wide; extra accounts/keys do not raise them.

**Free Models:**

- Roster rotates; any model ID ending in `:free` (representative, verify live via `GET https://openrouter.ai/api/v1/models` or https://openrouter.ai/models?max_price=0).
- Representative examples (secondary-reported): `openai/gpt-oss-20b:free`, `nvidia/nemotron-3-super-120b-a12b:free`, `cohere/north-mini-code:free`, `google/gemma-4-26b-a4b-it:free`.
- `openrouter/free` router auto-selects a free model.

**Limits:**

- Free variants: 20 requests/min always; 50 requests/day with < $10 lifetime purchased credits; 1,000 requests/day with >= $10 purchased credits (frontmatter `day: 50` is the no-purchase baseline).
- Paid variants have no platform request cap; DDoS protection applies to all requests.
- Negative credit balance returns 402 even on free models; 429 indicates a platform cap or upstream provider exhaustion (automatic provider fallback is attempted first).

**Notes:**

- Account required; API key required; no payment required for free models; phone verification: **unknown**.
- Fully OpenAI-compatible (`/api/v1/chat/completions`, `/api/v1/models`, `GET /api/v1/key` for quota/credit checks).
- Privacy: prompts/completions not logged by default (opt-in logging earns 1% discount); requests route only to providers matching the account's model-training privacy setting.
- Credit purchase fee ~5.5% via Stripe ($0.80 minimum) / 5% crypto; unused credits may expire after one year; refunds only within 24h.

**Sources**

- https://openrouter.ai/docs/api_reference/limits
- https://openrouter.ai/docs/faq
- https://openrouter.ai/docs/guides/routing/model-variants/free
- https://openrouter.ai/docs (quickstart)
- Secondary (example IDs only): docs/free-tier-research/raw/awesome-free-llm-apis/OpenRouter.json
